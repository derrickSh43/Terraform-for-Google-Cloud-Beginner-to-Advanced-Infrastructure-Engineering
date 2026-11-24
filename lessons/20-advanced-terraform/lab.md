# Lesson 20 Lab — Refactor a legacy repo without destroying anything

```powershell
python course.py start 20
python course.py check 20
```

The starter is the lesson 19 solution plus:

- `envs/dev/legacy_reporting.tf`: the reporting team's flat file (service account, reports bucket, writer grant, topic);
- an empty `modules/reporting/`;
- `state/dev.tfstate`: dev as deployed, including the legacy resources and a label someone added in the console.

Run the check on the starter first and read the dev plan: **0 to add, 1 to change**. Which
attribute changes, and who changed it? Don't apply anything yet.

Guard rails: R20.3 (nothing destroyed or replaced) and R20.7 (moved resources show no changes).

---

## Part A — Build the module

Nothing checks this part yet: Part B calls the module, and checks it then.

1. `modules/reporting/versions.tf`: `required_version >= 1.9.0` and `required_providers { google = { source = "hashicorp/google", version = ">= 8.0, < 9.0" } }`.
2. `modules/reporting/variables.tf`: `project_id`, `name_prefix`, `region`, `labels` (`map(string)`) and
   `retention_days` (number, default 90) with a `validation` that allows only **30–365**.
3. `modules/reporting/main.tf`: copy the four resources from `legacy_reporting.tf` and replace every
   literal: `project = var.project_id`, `name = "${var.name_prefix}-sales-reports"`,
   `location = upper(var.region)`, `labels = var.labels`, `age = var.retention_days`. **Keep the
   resource names** (`reporter`, `reports`, `reporter_writes`, `report_ready`): it makes the moves obvious.
4. `modules/reporting/outputs.tf`: `reports_bucket`, `reporter_email` (Part D adds `archive_bucket`).
5. `tests/lab/modules/reporting` ships a test that runs inside the module: 7 and 1095 days must be rejected.
   It also checks the archive bucket, so the `tests (modules/reporting)` stage stays red until Part D. That's expected.

## Part B — Move, don't recreate (R20.1 – R20.4, R20.9)

1. In `envs/dev/main.tf`, call the module with `project_id = var.project_id`, `name_prefix = local.name_prefix`,
   `region = var.region` and `retention_days = 90`.
2. **Delete `envs/dev/legacy_reporting.tf`.**
3. Run the check *now*, before adding any `moved` block. Read the plan: 4 to destroy, 4 to add. That's
   what a naive refactor would do to production data.
4. Create `envs/dev/refactor.tf` with one `moved` block per resource:

   ```hcl
   moved {
     from = google_storage_bucket.reports
     to   = module.reporting.google_storage_bucket.reports
   }
   ```

5. Check again: **0 to destroy**, and each resource shows *has moved to*.

## Part C — Adopt the console label (R20.7)

The plan still wants to update `module.reporting.google_storage_bucket.reports`:

```
~ labels = {
    - "cost-center" = "analytics" -> null
      "team"        = "reporting"
  }
```

Finance asked for that label. **Adopt it**: in dev, pass `labels = { team = "reporting", "cost-center" = "analytics" }`
(quote the key: it contains a hyphen). Do the same in prod.

## Part D — Import the archive bucket (R20.5, R20.6)

The reporting team created this bucket by hand. `gcloud storage buckets describe gs://meridian-dev-report-archive` shows:

```
name:                        meridian-dev-report-archive
location:                    US-CENTRAL1
default_storage_class:       NEARLINE
uniform_bucket_level_access: true
labels:                      cost-center=analytics, team=reporting
lifecycle_config:            rule: action=Delete, condition: age=730
```

1. Add `google_storage_bucket.archive` to the module, describing the bucket **exactly** as above,
   with the name built as `"${var.name_prefix}-report-archive"`. Add the output `archive_bucket`.
2. In `envs/dev/refactor.tf`:

   ```hcl
   import {
     to = module.reporting.google_storage_bucket.archive
     id = "meridian-dev-report-archive"
   }
   ```

3. Check. The plan line says `[1 imported (simulated)]`. If R20.6 lists attributes that differ,
   your configuration would *change* the real bucket: fix the configuration, not the bucket.
   Try leaving out `storage_class` once to see what that looks like.

## Part E — A post-condition (R20.8)

Add a `check` block to the module that asserts:

- the reports bucket uses uniform bucket-level access;
- every lifecycle rule deletes within 365 days (`alltrue([for r in google_storage_bucket.reports.lifecycle_rule : one(r.condition).age <= 365])`);
- the archive is not in `STANDARD` storage.

The plan output lists check results. A failing check is a **warning**, so the plan still succeeds;
R20.8 makes it a requirement.

## Part F — Prod (R20.10)

Call the same module in `envs/prod/main.tf`. Prod never had the legacy resources, so it needs **no**
`moved` or `import` blocks: its plan simply creates the reporting resources, archive included.

## Review

Dev: **Plan: 0 to add, 0 to change, 0 to destroy** `[1 imported (simulated)]`. A refactor that
lands as an empty plan is the goal.

## Reflection questions

1. A teammate's branch still has `legacy_reporting.tf`. They merge after you. What does their plan show, and why?
2. When can you delete the `moved` blocks? What changes if `modules/reporting` were used by other teams' repositories?
3. Why does R20.6 treat "the plan updates the imported bucket" as a failure, when an update is harmless for most attributes?
4. The `check` block fails next month: someone set a 2-year rule on the reports bucket in the console. The plan still succeeds. Is that good or bad?
5. `terraform import` (the command) or `import` blocks: which would you allow in a team with CI/CD from lesson 16, and why?
