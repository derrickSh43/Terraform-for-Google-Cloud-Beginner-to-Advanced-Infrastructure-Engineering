# Lesson 01 Lab — Your first bucket

```powershell
python course.py start 01
```

Work in `workspace/01-terraform-basics/`. Each step names the requirement IDs
that `python course.py check 01` verifies. Run the check whenever you like:
failing checks tell you what is missing and give a hint.

---

## Step 1 — Declare and pin the provider (R1.1)

Open `versions.tf`. Inside `required_providers`, declare the Google provider:

```hcl
google = {
  source  = "hashicorp/google"
  version = "~> 8.12"
}
```

Then initialize. This is the step that talks to the Terraform Registry:

```powershell
cd workspace/01-terraform-basics
terraform init
```

Look at the `.terraform.lock.hcl` file it created. It records the exact provider
version and checksums. In a real team you commit this file.

## Step 2 — Configure the provider from variables (R1.2, R1.3)

In `providers.tf`:

```hcl
provider "google" {
  project = var.project_id
  region  = var.region
}
```

In `variables.tf`, add a `region` variable with type `string`, default
`"us-central1"` and a description. `project_id` is already declared without a
default, so every environment *must* supply its own. Its value lives in
`terraform.tfvars`, which Terraform loads automatically.

## Step 3 — The bucket (R1.4 – R1.7)

In `main.tf`, add a `google_storage_bucket` that:

| Req | Setting |
|---|---|
| R1.4 | `name` built from the project ID, e.g. `"${var.project_id}-assets"`. Bucket names are global across *all* of Google Cloud. |
| R1.4 | `location` = your region (`upper(var.region)` works) |
| R1.5 | `uniform_bucket_level_access = true` and `public_access_prevention = "enforced"` |
| R1.6 | a nested `versioning { enabled = true }` block |
| R1.7 | `labels` with `app = "meridian"`, `env = var.environment`, `managed_by = "terraform"`. Declare the `environment` variable (default `"dev"`). |

Use the provider docs to find the argument names:
<https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/storage_bucket>

## Step 4 — Outputs and a data source (R1.8, R1.9)

In `outputs.tf`, add:

- `bucket_name` → the bucket's `.name`
- `bucket_url` → the bucket's `.url`

Then add a data source anywhere (e.g. `main.tf`):

```hcl
data "google_client_config" "current" {}
```

and an output `active_project` that reads `data.google_client_config.current.project`.

## Step 5 — The workflow

```powershell
terraform fmt          # rewrites files into canonical style
terraform validate     # catches typos, wrong types, bad references
python course.py check 01
```

Read the `plan` line in the report: *1 to add*. Now open
`.course/build/01l/plan.json` and find your bucket under
`resource_changes`. This JSON is what the checks read.

## Reflection questions

1. Delete `version = "~> 8.12"` and run `terraform init -upgrade`. What could go wrong in six months?
2. `bucket_url` refers to `google_storage_bucket.assets.url`. What does that tell Terraform about ordering?
3. Why does `project_id` have no default, when `region` does?
4. What would `terraform destroy` do if the bucket still contained files? Why is that good?

When every requirement passes, try [challenge.md](challenge.md).
