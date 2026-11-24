# Lesson 06 Challenge — Modules other teams can trust

Other teams want to use `vm-service`. Before you publish it, harden it.

```powershell
python course.py check 06 --challenge
```

| ID | Requirement |
|---|---|
| C6.1 | `vm-service` rejects any `machine_type` other than `e2-micro`, `e2-small` or `e2-medium`. `tests/challenge/vm_service_module.tftest.hcl` tests the module **on its own** and must pass. Read it: a `run` block can target a module directly with `module { source = "../../modules/vm-service" }`. |
| C6.2 | Every module under `modules/` declares its provider requirements in a `terraform { required_providers { ... } }` block: source plus a **range** (`">= 8.0, < 9.0"`), not an exact pin. Roots pin exactly; modules state compatibility. |
| C6.3 | Production VMs have `deletion_protection = true`. Dev VMs don't (dev should be easy to rebuild). Add a module variable and set it in prod's tfvars only. |
| C6.4 | Prod's web tier runs `e2-small`, dev stays `e2-micro`. Set it in tfvars, not with `if` logic in the module. Changing dev's size would show up as an update against the deployed state. |

## Contract for the test

The test calls the module with these inputs, so your `vm-service` must accept
them: `name, display_name, description, project_id, zone, subnet_id,
startup_script, labels`, optional `external_ip` (default `false`) and
`machine_type` (default `e2-micro`). Name the VM resource `google_compute_instance.this`.

## Think about it

- `deletion_protection` is an API-level guard. `prevent_destroy` is a Terraform-level guard. Which protects you from someone clicking **Delete** in the console?
- Why should a reusable module *not* pin `version = "8.12.0"` exactly?
