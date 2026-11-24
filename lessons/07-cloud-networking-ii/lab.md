# Lesson 07 Lab — NAT for the private tier, a peered ops network

```powershell
python course.py start 07
python course.py check 07
```

The starter is the lesson 06 solution plus `modules/peering/main.tf` (empty) and
`state/dev.tfstate`: dev as deployed after lesson 06. Before you change
anything, the dev plan reads `No changes`. Every change you make today is
reviewed against that live environment.

R7.4, R7.8 and R7.10 already pass on the starter. They are **guard rails**:
things that are true today and must stay true after your change.

`envs/dev/moved.tf` from lesson 06 is gone. Once the migration was applied,
the blocks had done their job.

---

## Part A — Outbound internet for the app tier (R7.1 – R7.4)

Run the check first. R7.3 explains the bug from the README:

```
app VM -> 151.101.2.132:443 should be ALLOWED, but is DENIED
  (app VM has no external IP and no Cloud NAT covers meridian-dev-app)
```

### Step 1: make NAT an option of the network module

In `modules/network/variables.tf`:

```hcl
variable "enable_nat" {
  description = "Create a Cloud Router and Cloud NAT so private VMs can reach the internet."
  type        = bool
  default     = false
}
```

In `modules/network/main.tf`, add a `google_compute_router` and a
`google_compute_router_nat`, both with `count = var.enable_nat ? 1 : 0`:

- router: `name = "${var.name_prefix}-router"`, `region = var.region`, `network = google_compute_network.this.id`
- NAT: `router = google_compute_router.this[0].name`, same region,
  `nat_ip_allocate_option = "AUTO_ONLY"`,
  `source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"`,
  and `log_config { enable = true  filter = "ERRORS_ONLY" }`

Add an output `nat_name = one(google_compute_router_nat.this[*].name)`, with a description.

### Step 2: turn it on

In both `envs/*/main.tf`, pass `enable_nat = true` to `module "network"`. Keep
`external_ip = true` only on the web tier (R7.4).

Check again. The dev plan should be *2 to add*, and R7.1–R7.4 pass.

## Part B — An ops VPC, peered (R7.5 – R7.7)

### Step 3: reuse the network module

Add `variable "ops_subnets"` (`map(string)`) to both environments. The values
go in tfvars: dev `{ tools = "10.110.0.0/24" }`, prod `{ tools = "10.120.0.0/24" }`.
Then:

```hcl
module "ops_network" {
  source = "../../modules/network"

  name_prefix = "${local.name_prefix}-ops"
  region      = var.region
  subnets     = var.ops_subnets

  depends_on = [module.foundation]
}
```

No new networking code. The module you wrote in lesson 06 builds a second VPC (R7.5).

### Step 4: the peering module

In `modules/peering/`, create **two** `google_compute_network_peering`
resources, A→B and B→A. Inputs: `network_a_id`, `network_b_id`, `name_a_to_b`,
`name_b_to_a`. Set `export_custom_routes` and `import_custom_routes` to `false`.
Make the second depend on the first, because GCP rejects concurrent peering
operations on the same networks.

Call it from both environments with `module.network.network_id` and
`module.ops_network.network_id` (R7.6).

### Step 5: let monitoring in

Peering adds routes, not permission. Add a rule to the firewall map:

```hcl
"allow-ops-monitoring" = {
  description   = "Monitoring in the peered ops VPC scrapes node exporter."
  source_ranges = values(var.ops_subnets)
  target_tags   = ["web", "app"]
  ports         = ["9100"]
}
```

Use the variable, not a hard-coded CIDR, so prod gets its own range automatically (R7.7).

## Part C — Review the change like a PR (R7.8 – R7.10)

The dev plan should now read **7 to add, 0 to change, 0 to destroy**:
router, NAT, ops VPC, ops subnet, two peerings, one firewall rule. Read the
plan output (`python course.py check 07 -v` shows full stage output) and confirm
that no existing VM, subnet or rule changes. Prod creates everything from scratch.

## Reflection questions

1. The web VM has an external IP *and* NAT covers its subnet. Which does it use for outbound traffic?
2. A third VPC (`security`) is peered with `ops`. Can it reach the app VM? Why not?
3. Why must peering ranges never overlap, while NAT doesn't care about overlap at all?
4. You set `enable_nat = false` in prod later. What does the plan show, and what happens to `nat_name`?
5. Is NAT a security control? What would an attacker on the app VM still be able to do?
