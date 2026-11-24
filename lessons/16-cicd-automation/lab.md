# Lesson 16 Lab — A keyless Terraform pipeline

```powershell
python course.py start 16
python course.py check 16
```

The starter is the lesson 15 solution plus `modules/github-oidc/main.tf` (empty),
`.github/workflows/terraform.yml` (a TODO comment) and `state/dev.tfstate`.
Treat your workspace folder as the root of a GitHub repository.

---

## Part A — Keyless identities (R16.1 – R16.3)

In `modules/github-oidc` (inputs: `project_id`, `repository`, `pool_id` = `meridian-github`,
`apply_service_account_email`, `plan_roles`):

1. `google_iam_workload_identity_pool` and an OIDC `google_iam_workload_identity_pool_provider`
   for `https://token.actions.githubusercontent.com`, mapping `google.subject`, `attribute.repository`
   and `attribute.ref`, with `attribute_condition = "assertion.repository == '${var.repository}'"`.
2. A plan identity, `meridian-ci-plan`, with **read-only** project roles (`plan_roles`):
   `compute.viewer`, `iam.securityReviewer`, `cloudsql.viewer`, `run.viewer`, `pubsub.viewer`,
   `container.viewer`, `secretmanager.viewer`, `serviceusage.serviceUsageViewer`, `artifactregistry.reader`.
3. `google_service_account_iam_member` bindings with `roles/iam.workloadIdentityUser`:
   - on the plan SA: `principalSet://iam.googleapis.com/${pool.name}/attribute.repository/${var.repository}`
   - on the apply SA (`"projects/${var.project_id}/serviceAccounts/${var.apply_service_account_email}"`):
     `principalSet://iam.googleapis.com/${pool.name}/attribute.ref/refs/heads/main`

Call it from both environments with `apply_service_account_email = module.ci.email` and
`repository = var.github_repository` (`meridianbooks/infrastructure`).

## Part B — The workflow (R16.4 – R16.8)

Write `.github/workflows/terraform.yml` with three jobs:

| Job | When | Does | Auth |
|---|---|---|---|
| `checks` | always | `terraform fmt -check -recursive`; `init -backend=false` + `validate` for `envs/dev`, `envs/prod`, `bootstrap`; `terraform test` in every module with a `tests/` folder | none |
| `plan` | `if: github.event_name == 'pull_request'`, `needs: checks`, matrix `env: [dev, prod]` | `init`, `plan -lock=false -out=tfplan` | plan identity |
| `apply` | `if: github.event_name == 'push' && github.ref == 'refs/heads/main'`, `needs: checks`, `environment: dev` | `init`, `apply -auto-approve` (dev) | apply identity |

- Triggers: `pull_request` and `push`, both on `branches: [main]`.
- Top level: `permissions: contents: read`. The plan and apply jobs add `id-token: write`.
- Authenticate with `google-github-actions/auth@v2` using `workload_identity_provider: ${{ vars.WIF_PROVIDER }}`
  and `service_account: ${{ vars.PLAN_SERVICE_ACCOUNT }}` (or `APPLY_SERVICE_ACCOUNT`). Never `credentials_json`.
- Each job starts with `actions/checkout@v4` and `hashicorp/setup-terraform@v3`.

The checker reads the workflow with a small YAML reader. Standard GitHub syntax works,
but anchors and aliases (`&`, `*`) don't.

## Part C — Test your own module (R16.9)

Create `modules/network/tests/network.tftest.hcl` with `mock_provider "google" {}` and
at least **3 `run` blocks and 5 assertions**. Ideas: one subnet per tier with the right
names, custom-mode VPC, no NAT by default, NAT when `enable_nat = true`, secondary ranges only
on the requested subnet. The checker runs them: look for the `tests (modules/network)` stage.

Run them yourself too:

```powershell
terraform -chdir=workspace/16-cicd-automation/modules/network init -backend=false
terraform -chdir=workspace/16-cicd-automation/modules/network test
```

## Review

Dev: **14 to add, 0 to change, 0 to destroy**. Then read your workflow as an attacker
who can open a pull request. What can they make it do?

## Reflection questions

1. A contributor's PR edits the workflow and removes the apply job's `if:`. What stops their code from applying to dev? (Two independent answers.)
2. Why may PR plans use `-lock=false`, but apply must never?
3. Why does the checks job need no Google credentials at all? What does that buy you?
4. The plan identity can read secret *metadata* (`secretmanager.viewer`). Why not `secretAccessor`?
