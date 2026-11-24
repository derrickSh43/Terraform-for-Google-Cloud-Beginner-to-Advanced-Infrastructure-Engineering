# Lesson 04 Challenge — Subnets as data

Meridian will add tiers (app, data, batch...). Writing a new resource block each
time doesn't scale.

```powershell
python course.py check 04 --challenge
```

| ID | Requirement |
|---|---|
| C4.1 | Replace `web_subnet_cidr` with `variable "subnets"` (`map(string)`, tier name → CIDR) defaulting to `web = 10.10.1.0/24` and `app = 10.10.2.0/24`. Create **all** subnets from one resource with `for_each`. The VM uses the `"web"` entry. |
| C4.2 | No two subnets may overlap. |
| C4.3 | Enable VPC flow logs on every subnet (sample 50%, include metadata). |
| C4.4 | Validate `var.subnets`: every value must be a valid CIDR, and a `web` key is mandatory. `tests/challenge/subnets.tftest.hcl` must pass. |

## Hints

- Instances are addressed by key: `google_compute_subnetwork.tier["web"].id`.
- `alltrue([for c in values(var.subnets) : can(cidrnetmask(c))])`
- `contains(keys(var.subnets), "web")`
- A variable can have **several** `validation` blocks.

## Think about it

If you renamed the resource from `web` to `tier`, a real apply would *destroy
and recreate* the subnet, and with it the VM. Lesson 20 teaches `moved` blocks,
which tell Terraform it's the same object under a new address.
