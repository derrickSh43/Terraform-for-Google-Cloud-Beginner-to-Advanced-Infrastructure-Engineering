# Lesson 06 Lab — Modules, remote state, and a zero-downtime refactor

```powershell
python course.py start 06
python course.py check 06
```

Your starter:

```
legacy/          lesson 05 solution: the code that built the deployed dev env (read, then retire)
state/dev.tfstate  what's deployed in dev right now (20 resources)
scripts/         startup scripts, now shared by every environment
modules/         four empty modules (TODO)
envs/dev/  envs/prod/   providers, variables and tfvars ready; main.tf, backend.tf, outputs.tf TODO
bootstrap/       providers and variables ready; main.tf TODO
```

Run the check before writing anything. Look at the dev plan line:

```
PASS  plan (dev)   Plan: 0 to add, 0 to change, 20 to destroy  [against deployed state]
```

An empty dev root plus the deployed state means *destroy everything*. Your job is
to get that to **0 / 0 / 0**.

> **Contract:** keep the network tags `web` and `app` on the VMs, and use a map
> for subnets with keys `web` and `app` (the tfvars already do).

---

## Part A — Shared state (R6.1 – R6.3)

### Step 1: bootstrap the state bucket

In `bootstrap/main.tf`, create one `google_storage_bucket` named
`"${var.project_id}-tfstate"` with:

- `versioning { enabled = true }`
- `uniform_bucket_level_access = true`, `public_access_prevention = "enforced"`
- a `lifecycle_rule` that deletes archived versions once 20 newer versions exist (optional, but good practice)
- `lifecycle { prevent_destroy = true }`. `terraform destroy` then refuses to delete it.

With `project_id = "meridian-ops-1002"` the bucket is `meridian-ops-1002-tfstate`.

### Step 2: point the environments at it

`envs/dev/backend.tf`:

```hcl
terraform {
  backend "gcs" {
    bucket = "meridian-ops-1002-tfstate"
    prefix = "envs/dev"
  }
}
```

Do the same for prod with `prefix = "envs/prod"`. Backend blocks can't use
variables, which is why the bucket name is a literal.

## Part B — Write the modules (R6.5 – R6.7, R6.10)

Move code out of `legacy/` into modules. Each module gets `main.tf`,
`variables.tf` and `outputs.tf`, with **a description on every variable and
output** (R6.7). No `provider` blocks inside modules.

| Module | Contains | Suggested inputs → outputs |
|---|---|---|
| `foundation` | `google_project_service` (for_each), the assets bucket, `data "google_client_config"` | `project_id, region, labels, apis` → `bucket_name, bucket_url, active_project` |
| `network` | VPC + `google_compute_subnetwork` **for_each over `var.subnets`** | `name_prefix, region, subnets` → `network_id, subnet_ids` (map) |
| `firewall` | **one** `google_compute_firewall` with for_each over a map of rule objects | `name_prefix, network_id, rules` → `rule_names` |
| `vm-service` | service account + IAM members + VM | `name, display_name, description, project_id, zone, subnet_id, external_ip, startup_script, labels` → `service_account_email, internal_ip, external_ip` |

Tips:

- The firewall `rules` variable type is a map of objects. Use `optional(...)` for fields not every rule needs:
  ```hcl
  type = map(object({
    description   = string
    priority      = optional(number, 1000)
    source_ranges = optional(list(string))
    source_tags   = optional(list(string))
    target_tags   = list(string)
    protocol      = optional(string, "tcp")
    ports         = list(string)
  }))
  ```
- In `vm-service`, only the web tier has an external IP. A `dynamic "access_config"` block with
  `for_each = var.external_ip ? [1] : []` handles both.
- `merge(var.labels, { role = var.name })` adds the role label.
- **Names must match what's deployed**: `meridian-dev-vpc`, `meridian-dev-web`, `meridian-dev-allow-http`,
  `meridian-web`, `meridian-web-1` and so on. Changing a name forces Terraform to replace the resource.

Then write `envs/dev/main.tf`: a `locals` block (name prefix, labels) and **only
module calls** (R6.5; R6.4 checks both environments, so it passes in Part D). Call `vm-service` twice, as `web` and `app` (R6.6).
Pass startup scripts as content: `file("${path.root}/../../scripts/startup.sh")`.
Copy the lesson 05 outputs into `envs/dev/outputs.tf`, reading from module outputs.

Run the check. The plan should now say roughly *20 to add, 20 to destroy*.
Same infrastructure, new addresses.

## Part C — Migrate dev without destroying it (R6.8)

List what's deployed:

```powershell
terraform state list -state=state/dev.tfstate
```

For every old address, write a `moved` block in `envs/dev/moved.tf`:

```hcl
moved {
  from = google_compute_subnetwork.web
  to   = module.network.google_compute_subnetwork.this["web"]
}
```

`for_each` resources can be moved whole when the keys stay the same:

```hcl
moved {
  from = google_project_service.apis
  to   = module.foundation.google_project_service.apis
}
```

Re-run the check until dev reads **`Plan: 0 to add, 0 to change, 0 to destroy`**.
If R6.8 fails, it lists every resource that would be destroyed, created or
replaced, plus the `moved` blocks it can infer, and for replacements the
attribute that forces them (usually a name you changed).

## Part D — Production (R6.4, R6.9)

`envs/prod/` gets the same `main.tf` and `outputs.tf` as dev. The only
differences are `terraform.tfvars` (already written: its own project, `environment = "prod"`,
`10.20.0.0/16`) and the backend prefix. Prod has no state, so its plan creates
20 resources. It needs **no** `moved.tf`.

Finally, `legacy/` has done its job. In a real repo you'd delete it in this PR.
The checker ignores it.

## Reflection questions

1. Why can't a backend block use `var.state_bucket`? How do teams usually work around that? (Look up `-backend-config`.)
2. You remove `"app"` from `var.subnets`. With `for_each`, what happens to `this["web"]`? What would happen with `count` and a list?
3. After this PR is applied to dev, can the `moved` blocks be deleted? What about for teammates whose branches still use old addresses?
4. Two engineers run `terraform apply` on dev at the same moment. What does the GCS backend do?
5. State contains every attribute. Where would a database password end up if lesson 12 created one?
