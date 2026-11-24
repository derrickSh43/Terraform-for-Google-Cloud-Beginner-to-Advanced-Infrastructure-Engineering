# Lesson 11 Challenge — Backups that survive anything

```powershell
python course.py check 11 --challenge
```

| ID | Requirement |
|---|---|
| C11.1 | Compliance requires that production backups can't be deleted early **by anyone, ever**. Add a `lock_backup_retention` variable to `foundation` and lock the retention policy in **prod only**. Dev must stay unlocked. |
| C11.2 | prod backups must survive a regional outage. Make the prod backups bucket **dual-region**: `location = "US"` with `custom_placement_config { data_locations = ["US-CENTRAL1", "US-EAST1"] }`, behind a `backup_dual_region` variable. |
| C11.3 | Snapshots are regional by default. Store them in the **`us` multi-region** with `snapshot_properties { storage_locations = ["us"] }`, so a disk can be restored in another region. |
| C11.4 | `vm-service` must reject silly disk sizes: `0` (no disk) or 10–1000 GB. `tests/challenge/vm_service_disk.tftest.hcl` tests the module with no disk, a 20 GB disk and a 5 GB disk. |

## Think about it

- Once prod's retention is locked, what happens if someone sets `backup_retention_days = 7` next year? (Look up "retention policy lock" behaviour.)
- Changing a bucket's location forces Terraform to **replace** the bucket. Why is that fine for prod here, but would be a serious problem against a deployed prod with data in it?
