# Lesson 23 Lab — A landing zone for every team

```powershell
python course.py start 23
python course.py check 23
```

The starter is the lesson 22 solution, plus:

- a new root `envs/platform` (backend, provider, variables, and `terraform.tfvars` with four projects);
- three empty modules: `landing-zone`, `project-factory` and `central-logging`.

Guard rail: R23.10, dev's plan stays at *No changes*.

The `tests (modules/project-factory)` stage stays red until you write that module in Part B. That's expected.

---

## Part A — The hierarchy (R23.1, R23.8, R23.9)

`modules/landing-zone` (inputs `org_id`, `platform_group`, `developer_group`, plus defaults for
`environments`, `boolean_constraints`, `developer_roles`):

1. `google_folder.meridian` under `organizations/${var.org_id}`, and `google_folder.env` (for_each
   dev/prod/shared) under it, both with `deletion_protection = true`.
2. `google_org_policy_policy.enforced` for each boolean constraint, with
   `parent = google_folder.meridian.name` and `name = "${google_folder.meridian.name}/policies/<constraint>"`.
3. `google_folder_iam_member`: `roles/resourcemanager.folderAdmin` for the platform group on Meridian;
   `developer_roles` for the developers group on the **dev** folder only.
4. Outputs `meridian_folder` and `env_folders` (a map: env → `folders/<id>`).
5. Call it in `envs/platform/main.tf` as `module "landing_zone"`, with the root's variables.

## Part B — The project factory (R23.2 – R23.5)

`modules/project-factory` (inputs `billing_account`, `folders`, `shared_vpc_host`, `projects`):

1. `projects` is a `map(object({ folder, env, cost_center, owner, budget, apis = optional(list(string), []), shared_vpc = optional(bool, false) }))`
   with validations: env in dev/prod/shared, `cost_center` matches `^cc-[0-9]{4}$`, owner not blank, budget > 0.
2. `google_project.this` (for_each): `project_id = "${each.key}-${random_id.suffix[each.key].hex}"`,
   `folder_id = var.folders[each.value.folder]`, labels `app`, `env`, `cost-center`, `owner`, `managed_by`,
   `auto_create_network = false`, `deletion_policy = "PREVENT"`.
3. `google_project_service` for each project's APIs (flatten the map of lists into one map).
4. `google_billing_budget.this` (for_each): scoped with `budget_filter { projects = ["projects/${google_project.this[each.key].number}"] }`,
   amount in USD, thresholds 0.5, 0.9, 1.0 and 1.0 `FORECASTED_SPEND`.
5. `google_compute_shared_vpc_host_project` for `var.shared_vpc_host`, and
   `google_compute_shared_vpc_service_project` `this` for each project with `shared_vpc = true`.
6. Output `project_ids` (a map: project key → project ID).
7. Call it in `envs/platform/main.tf` as `module "projects"`, with `folders = module.landing_zone.env_folders`
   and `shared_vpc_host = "meridian-network"`.
8. The lesson test `tests/lab/modules/project-factory` must pass: it feeds in bad labels.

## Part C — Central logging (R23.6, R23.7)

`modules/central-logging` (inputs `folder`, `logging_project_id`, `retention_days = 400`):

1. `google_logging_project_bucket_config` `meridian-central` in the logging project, `location = "global"`.
2. `google_logging_folder_sink` on the Meridian folder, `include_children = true`,
   `destination = "logging.googleapis.com/${google_logging_project_bucket_config.central.id}"`.
3. `google_project_iam_member`: `roles/logging.bucketWriter` for the sink's `writer_identity`.
4. Call it in `envs/platform/main.tf` as `module "central_logging"`, with
   `folder = module.landing_zone.meridian_folder` and
   `logging_project_id = module.projects.project_ids["meridian-logging"]`.

## Review

Platform: **40 to add**. Dev: **No changes**. Try `cost_center = "marketing"` in the tfvars and
read the error: that's the validation doing finance's job.

## Reflection questions

1. A team asks for Owner on their prod project "just for a day". Where would you grant it, and how would you make it expire? (Hint: IAM conditions.)
2. Why does the sink need its own grant, when you (the person applying) are already an admin?
3. `deletion_policy = "PREVENT"`: how would you really delete a project, and who should be allowed to?
4. The existing `meridian-dev-4821` and `meridian-prod-7730` projects were made by hand in 2023. How would you bring them into the factory and the hierarchy without downtime? (Lesson 20's tools.)
5. Budgets alert but don't cap. Make the case for and against an automatic cap on dev projects.
