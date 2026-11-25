# Lesson 11 Lab — Durable data for the app tier

```powershell
python course.py start 11
python course.py check 11
```

The starter is the lesson 10 solution with `state/dev.tfstate` (dev as deployed
after lesson 10). There are no new stub files: you extend the existing
`vm-service` and `foundation` modules. R11.8 is a guard rail. Nothing deployed
may be destroyed or replaced.

`envs/dev/moved.tf` from lesson 10 has been applied, so you may delete it.

---

## Part A — A data disk with snapshots (R11.1 – R11.4)

All of this goes in `modules/vm-service`, switched on by a new variable
`data_disk_size_gb` (default `0` = no disk). Also add `snapshot_retention_days` (default `7`). Use `count = var.data_disk_size_gb > 0 ? 1 : 0`
on every new resource.

1. `google_compute_disk` `data`: `name = "meridian-${var.name}-data"`, `zone = var.zone`,
   `type = "pd-balanced"`, `size = var.data_disk_size_gb`, labels, and
   `lifecycle { prevent_destroy = true }` (R11.4).
2. `google_compute_attached_disk`: `disk = google_compute_disk.data[0].id`,
   `instance = google_compute_instance.this.id` (R11.2).
3. In the **existing** `google_compute_instance.this`, add
   `lifecycle { ignore_changes = [attached_disk] }`. Read the README section
   "Attaching without recreating" to see why.
4. `google_compute_resource_policy` `snapshots` with a daily `snapshot_schedule_policy`,
   `max_retention_days = var.snapshot_retention_days`, and `on_source_disk_delete = "KEEP_AUTO_SNAPSHOTS"`.
   Resource policies are regional. Derive the region from the zone:
   `join("-", slice(split("-", var.zone), 0, 2))`.
5. `google_compute_disk_resource_policy_attachment` linking the two (R11.3).

In both environments pass `data_disk_size_gb = 20` and
`snapshot_retention_days = var.snapshot_retention_days` to `module "app"` (dev 7, prod 14).

> ⚠️ Don't edit `scripts/app-startup.sh` to format the disk.
> `metadata_startup_script` is ForceNew, so the deployed app VM would be **replaced**.
> Try it and watch R11.8 fail. Then undo it.

## Part B — A backups bucket (R11.5, R11.6, R11.9)

In `modules/foundation`, add `google_storage_bucket` `backups` (`"${var.project_id}-backups"`):

- uniform access, `public_access_prevention = "enforced"`, `force_destroy = false`, **no** versioning
- `retention_policy { retention_period = var.backup_retention_days * 86400  is_locked = false }`
- lifecycle rules: NEARLINE at age 30, COLDLINE at age 90, Delete at age 365
- output `backups_bucket`

Environments: `backup_retention_days` (dev 7, prod 30).

The app tier writes backups. Add `writable_buckets` (`list(string)`, default `[]`) to `vm-service`,
with a `google_storage_bucket_iam_member` per bucket and `roles/storage.objectCreator`.
Pass `[module.foundation.backups_bucket]` to the app.

## Part C — Old asset versions (R11.7)

The assets bucket keeps every overwrite forever (versioning since lesson 01).
Add a lifecycle rule that deletes noncurrent versions after 30 days. This
updates the deployed bucket **in place**.

## Review

`python course.py check 11 -v`. Dev should be **6 to add, 1 to change, 0 to destroy**.
The app VM must **not** appear in the plan at all.

## Reflection questions

1. You recreate the app VM next month for a new image. What happens to the data disk, and what must you do afterwards?
2. Why does `on_source_disk_delete = "KEEP_AUTO_SNAPSHOTS"` matter more than the snapshot schedule itself?
3. The app can create objects in backups but not delete them. Who *can* delete a 3-day-old backup? (Trick question.)
4. Why can't you move objects to Nearline after 7 days to save money sooner?
5. `prevent_destroy` blocks `terraform destroy`. What doesn't it protect against?
