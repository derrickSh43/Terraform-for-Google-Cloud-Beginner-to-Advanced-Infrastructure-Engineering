# Lesson 22 Challenge — Ready to fail over

```powershell
python course.py check 22 --challenge
```

| ID | Requirement |
|---|---|
| C22.1 | **Replica sized for the job.** After promotion the replica serves everything: same `tier` as the primary, and `deletion_protection_enabled = true` in its settings (API-level protection, on top of Terraform's). |
| C22.2 | **Generated failover steps.** A prod output `failover_commands`: `gcloud sql instances promote-replica <replica>` (built from `module.db.replica_name`, never typed), and the command that rebuilds compute in `var.dr_region`. Empty when there is no DR region. |
| C22.3 | **Backups out of the region.** `backup_configuration.location = "us"` on the prod primary (a `backup_location` input to `postgres`, null in dev), so restores don't depend on Google's default choice. |
| C22.4 | **Guard rail.** `postgres` rejects a `dr_region` equal to `region`. The lesson test runs inside `modules/postgres` (`tests/challenge/modules/postgres`). |

## Think about it

- Generated commands go stale less often than a wiki page. What else in your runbook could be generated from configuration?
- After a real failover, us-central1 comes back. Do you fail back? What would you have to rebuild, and in what order?
- C22.4 stops one mistake. What other DR misconfiguration could a validation or a `check` block catch?
