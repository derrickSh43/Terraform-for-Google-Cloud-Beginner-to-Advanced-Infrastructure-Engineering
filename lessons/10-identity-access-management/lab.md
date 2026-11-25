# Lesson 10 Lab — Fix the audit findings

```powershell
python course.py start 10
python course.py check 10
```

The starter is the lesson 09 solution plus:

- `envs/dev/legacy-access.tf`: the audited mess. It's **deployed**: it's in `state/dev.tfstate`.
- `modules/ci-identity/main.tf` and `modules/project-access/main.tf`: empty.

R10.8 and R10.9 already pass. They're guard rails: the workload accounts and
the CI account must survive your cleanup.

---

## Part A — Read the findings

Open `envs/dev/legacy-access.tf` and match each resource to a finding:

| # | Finding | Requirement |
|---|---|---|
| 1 | CI holds `roles/editor` | R10.2, R10.4 |
| 2 | A JSON key exists for CI, and an output exposes it | R10.1 |
| 3 | An authoritative `google_project_iam_binding` | R10.3 |
| 4 | `user:sam.contractor@example.com` is Owner | R10.2 |
| 5 | Humans can only act as CI by using the key | R10.6 |

Run `terraform state list -state=state/dev.tfstate` from your workspace root to
see them as deployed objects.

## Part B — A proper CI identity

R10.4 – R10.6 are checked in Part C: until the legacy file is gone there are two
`meridian-ci` accounts.

In `modules/ci-identity/` (inputs `project_id`, `assets_bucket` and `impersonators`; give every other variable a default,
including `permissions`, the list in step 2):

1. `google_service_account.this`: `account_id = var.account_id` (default `meridian-ci`),
   `display_name = "CI pipeline"`. Same values as the deployed account.
2. `google_project_iam_custom_role.deployer` with `permissions = var.permissions`, an explicit list. CI rolls the web MIG to a new template:

   ```
   compute.instanceGroupManagers.get      compute.instanceGroupManagers.update
   compute.instanceTemplates.get          compute.instanceTemplates.list
   compute.instanceTemplates.useReadOnly  compute.instances.list
   compute.regionOperations.get
   ```

   Grant it with `google_project_iam_member` (`role = google_project_iam_custom_role.deployer.id`).
3. `google_storage_bucket_iam_member` on `var.assets_bucket` with `roles/storage.objectAdmin`.
   CI publishes static assets there and nowhere else.
4. `google_service_account_iam_member` (for_each over `var.impersonators`):
   `service_account_id = google_service_account.this.name`, `role = "roles/iam.serviceAccountTokenCreator"`.

Call it from both environments with `assets_bucket = module.foundation.bucket_name`
and `impersonators = var.ci_impersonators`
(`["group:meridian-platform@meridianbooks.example"]` in tfvars).

## Part C — Retire the legacy file safely (R10.1 – R10.6, R10.8, R10.9)

1. Delete `envs/dev/legacy-access.tf`.
2. Keep the CI account. The CI system knows its unique ID. Move it:

   ```hcl
   moved {
     from = google_service_account.ci
     to   = module.ci.google_service_account.this
   }
   ```
3. Run the check with `-v`. The dev plan should read **0 to change, 4 to destroy**, and should say `google_service_account.ci has moved to module.ci.google_service_account.this`.
   The four destroys are the key, the editor grant, the binding and the owner grant.

Confirm R10.8: deleting the authoritative binding must leave the web and app
`logWriter` grants from earlier lessons intact.

## Part D — Human access through groups (R10.7, R10.10)

`modules/project-access/`: one variable `group_roles` (`map(list(string))`, group → roles).
Flatten it into one `google_project_iam_member` per pair:

```hcl
locals {
  grants = {
    for pair in flatten([
      for principal, roles in var.group_roles : [
        for role in roles : { principal = principal, role = role }
      ]
    ]) : "${pair.principal} ${pair.role}" => pair
  }
}
```

Add validations: keys must start with `group:`, and no basic roles.
dev: developers get `roles/compute.viewer` and `roles/logging.viewer`.
prod: `roles/logging.viewer` only (R10.10).

The finished dev plan is **6 to add, 0 to change, 4 to destroy**.

## Reflection questions

1. Why is `roles/storage.objectAdmin` on the bucket safer than the same role on the project? Name one bucket CI must never touch.
2. You grant `serviceAccountTokenCreator` at project level "to save time". What can the platform group now do that it couldn't before?
3. CI needs one more permission next month. What's the review process, and why is that better than `roles/editor`?
4. Where does a removed contractor's access survive if it was granted through a group they're still in?
