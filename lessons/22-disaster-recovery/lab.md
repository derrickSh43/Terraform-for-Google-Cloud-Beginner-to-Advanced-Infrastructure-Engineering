# Lesson 22 Lab — Survive the loss of a region

```powershell
python course.py start 22
python course.py check 22
```

The starter is the lesson 21 solution, `state/dev.tfstate` (dev after lesson 21) and
`envs/prod/DR-NOTES.md`. Guard rail: **R22.9**, dev's plan must stay at *No changes* the whole time.

The business agreed these objectives for a loss of `us-central1`:

| Data store | RPO | RTO |
|---|---|---|
| database | 5 min | 60 min |
| backups | 15 min | 240 min |
| images | 0 | 60 min |

---

## Part A — Write the objectives down (R22.1)

1. In both environments, declare `dr_region` (default `null`) and
   `recovery_objectives` (`map(object({ rpo_minutes = number, rto_minutes = number }))`, default `{}`).
2. In prod's `terraform.tfvars`, set `dr_region = "us-east1"` and the three objectives above.
3. Run the check. R22.7 still fails, and tells you, per data store, what this configuration would actually lose.
   Keep it open while you work: it passes after Part D.

## Part B — The database (R22.2)

In `modules/postgres`, add `dr_region` and a `google_sql_database_instance.replica` with
`count = var.dr_region == null ? 0 : 1`:

- `master_instance_name = google_sql_database_instance.this.name`;
- `region = var.dr_region`, same `database_version`;
- private IP only, on `var.network_id`;
- `deletion_protection = true`.

Pass `dr_region = var.dr_region` from both roots. Add an output `replica_name`.

## Part C — Backups, audit logs and keys (R22.3 – R22.5)

1. `foundation`: a `storage_location` input (default `null`) for the backups bucket
   (`location = upper(coalesce(var.storage_location, var.region))`), and `turbo_replication`
   (`rpo = var.turbo_replication ? "ASYNC_TURBO" : null`).
2. `observability`: the same `storage_location` for the audit bucket.
3. `kms`: a `location` input for the key ring (`lower(coalesce(var.location, var.region))`).
4. Roots: declare `storage_location` and `turbo_replication`, and pass them to all three modules.
   Prod: `storage_location = "NAM4"`, `turbo_replication = true`.

Re-run the check after each step. If dev shows a replacement, a default isn't the old behaviour.
Try it once: add `storage_location = "NAM4"` to **dev's** tfvars. The plan fails: moving the key ring
would replace the KMS key, and lesson 19's `prevent_destroy` refuses. The backups bucket would have
been replaced too, with its data. Remove the line again.

## Part D — Images (R22.6, R22.7)

`artifact-repo`: a `location` input (`coalesce(var.location, var.region)`); roots pass
`registry_location`; prod sets `"us"`.

## Part E — Prove it (R22.8, R22.10)

R22.8 removes `us-central1` from prod and lists any critical data store with no copy left.

## Review

Dev: **No changes**. Prod: database, backups, audit logs and images all survive losing us-central1,
and every RPO is met. What *isn't* protected? The assets bucket and the reporting buckets are
still regional. Decide whether that's acceptable, and write down why.

## Reflection questions

1. The replica is in us-east1, but the app VMs are rebuilt there only after an incident. Walk through the first 60 minutes of a region outage. Where does the RTO go?
2. Why can't a cross-region replica give an RPO of 0? What would?
3. You promote the replica. What happens to it in Terraform state, and what must you change in the configuration afterwards?
4. Turbo replication guarantees 15 minutes. Why not use it on every bucket?
5. Changing `storage_location` on an existing bucket would replace it. How would you move dev's backups to a dual-region without losing them?
