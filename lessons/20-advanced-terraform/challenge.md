# Lesson 20 Challenge — Hand over, bulk import, protect

```powershell
python course.py check 20 --challenge
```

| ID | Requirement |
|---|---|
| C20.1 | **Hand the topic over.** The events team now manages `sales-report-ready` in their own configuration. Remove the topic from the module and replace its `moved` block with `removed { from = google_pubsub_topic.report_ready  lifecycle { destroy = false } }`. The plan shows the topic as **forget** (Terraform 1.7+), not destroy, and prod no longer creates one. |
| C20.2 | **Bulk import.** The auditors' quarterly export buckets `meridian-dev-export-2025-q3` and `meridian-dev-export-2025-q4` were also made by hand (`COLDLINE`, uniform access, the same labels, no lifecycle rules). Add `google_storage_bucket.exports` with `for_each = toset(var.export_quarters)` and adopt both buckets with **one** import block: `for_each`, `to = module.reporting.google_storage_bucket.exports[each.key]`, `id = "meridian-dev-export-${each.key}"`. Dev sets `export_quarters = ["2025-q3", "2025-q4"]`; prod sets `[]`. |
| C20.3 | **Protect adopted data.** `lifecycle { prevent_destroy = true }` on the archive and export buckets. |
| C20.4 | **Validate quarters.** `export_quarters` values must match `^20[0-9]{2}-q[1-4]$`. The lesson test runs inside `modules/reporting` (`tests/challenge/modules/reporting`). |

The offline import simulator evaluates `for_each` when it's a literal (or a local holding one),
not `var.*`. Real Terraform accepts any value known at plan time.

## Think about it

- `removed` with `destroy = false` and `terraform state rm` both stop Terraform managing an object. Why is the block better in a team?
- With `prevent_destroy`, how do you delete an export bucket when the auditors are done with it? List the steps.
- The events team imports the topic into their configuration on the same day you merge C20.1. In what order must the two applies happen, and what goes wrong if they're reversed?
