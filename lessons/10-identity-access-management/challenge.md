# Lesson 10 Challenge — Keyless, temporary, enforced

```powershell
python course.py check 10 --challenge
```

| ID | Requirement |
|---|---|
| C10.1 | **Workload Identity Federation for GitHub Actions.** In `ci-identity`, when `var.github_repository` is set (`meridianbooks/infrastructure`), create a `google_iam_workload_identity_pool`, an OIDC `google_iam_workload_identity_pool_provider` for `https://token.actions.githubusercontent.com` with an `attribute_condition` that accepts **only that repository**, and grant `roles/iam.workloadIdentityUser` on `meridian-ci` to `principalSet://iam.googleapis.com/<pool name>/attribute.repository/<repo>`. |
| C10.2 | **Human access expires.** Add an optional `expires` (RFC 3339) to `project-access`. When set, every grant carries an IAM condition `request.time < timestamp("...")`. Environments use `2027-06-30T00:00:00Z`. |
| C10.3 | **Make keys impossible**, not just absent. A `guardrails` module with a `google_org_policy_policy` enforcing `iam.disableServiceAccountKeyCreation` on the project. |
| C10.4 | **The CI module refuses dangerous permissions.** A validation on `var.permissions` rejects wildcards, `*.setIamPolicy`, `iam.*` and `resourcemanager.*`. `tests/challenge/ci_identity_module.tftest.hcl` must pass. |

## Contract for the lesson test

The test calls the module on its own with `project_id`, `assets_bucket` and `impersonators`, so every other variable needs a
default (`github_repository` defaults to `""`: no federation). It looks for
`google_project_iam_custom_role.deployer` and `google_iam_workload_identity_pool.github` (with `count`).

## Hints

- Without `attribute_condition`, **any** GitHub repository's workflow can exchange its token with your pool. This is the most common WIF misconfiguration.
- A dynamic `condition` block: `for_each = var.expires == "" ? [] : [var.expires]`.
- `strcontains`, `startswith` and `endswith` are built-in functions.

## Think about it

C10.3 enforces at the API, so even an Owner can't create a key. Why is a
preventive control like this stronger than a detective one, such as an alert when a key is created?
