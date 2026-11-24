# Lesson 15 Lab — A private Autopilot cluster for batch jobs

```powershell
python course.py start 15
python course.py check 15
```

The starter is the lesson 14 solution plus an empty `modules/gke-autopilot`
and `state/dev.tfstate` (dev after lesson 14). R15.9 is a guard rail: it also
fails if an existing subnet changes.

---

## Part A — IP space (R15.1)

1. Add `container.googleapis.com` to the foundation APIs.
2. `modules/network`: a variable `secondary_ranges` (`map(map(string))`, tier → { name → CIDR },
   default `{}`) and, inside the subnet resource:

   ```hcl
   dynamic "secondary_ip_range" {
     for_each = lookup(var.secondary_ranges, each.key, {})
     content {
       range_name    = secondary_ip_range.key
       ip_cidr_range = secondary_ip_range.value
     }
   }
   ```
3. tfvars: a `gke` subnet plus its secondary ranges.

   | | `gke` subnet | pods | services | control plane |
   |---|---|---|---|---|
   | dev | 10.10.32.0/22 | 10.11.0.0/17 | 10.11.128.0/22 | 172.16.0.0/28 |
   | prod | 10.20.32.0/22 | 10.21.0.0/17 | 10.21.128.0/22 | 172.16.1.0/28 |

   Pass `secondary_ranges = var.secondary_ranges` to `module "network"`.

Check now. The dev plan should add one subnet (plus the API) and change nothing else. R15.2 checks
the ranges through the cluster that uses them, in Part B.

## Part B — The cluster module (R15.2 – R15.5, R15.7)

In `modules/gke-autopilot`:

1. A node service account (`"${var.name}-nodes"`) with **only** `roles/container.defaultNodeServiceAccount`.
2. `google_container_cluster`:
   - `enable_autopilot = true`, `location = var.region`, `deletion_protection = true`, `network`, `subnetwork`
   - `ip_allocation_policy { cluster_secondary_range_name = "pods"  services_secondary_range_name = "services" }`
   - `private_cluster_config { enable_private_nodes = true  enable_private_endpoint = true  master_ipv4_cidr_block = var.master_cidr }`
   - `master_authorized_networks_config` with a `dynamic "cidr_blocks"` over `var.authorized_networks`
   - `workload_identity_config { workload_pool = "${var.project_id}.svc.id.goog" }`
   - `release_channel { channel = var.release_channel }`
   - `maintenance_policy { recurring_window { start_time, end_time, recurrence = "FREQ=WEEKLY;BYDAY=SA,SU" } }`
   - `cluster_autoscaling { auto_provisioning_defaults { service_account = <node SA>  oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"] } }`
3. Workload identities: for each entry of `var.workloads` (`"reports" = "batch/report-generator"`),
   a `google_service_account` `meridian-<key>` and a `google_service_account_iam_member` with
   `roles/iam.workloadIdentityUser` for `"serviceAccount:${var.project_id}.svc.id.goog[${each.value}]"`.

Outputs: `cluster_name`, `node_service_account`, `workload_service_accounts` (map).

Call it from both environments, with `gke_master_cidr` and `gke_release_channel` in tfvars
(dev `REGULAR`, prod `STABLE`):

```hcl
module "batch_cluster" {
  source              = "../../modules/gke-autopilot"
  name                = "${local.name_prefix}-batch"
  subnet_id           = module.network.subnet_ids["gke"]
  authorized_networks = var.ops_subnets            # kubectl only from the ops VPC
  workloads           = { reports = "batch/report-generator" }
  # project_id, region, network_id, master_cidr, release_channel, labels
}
```

## Part C — Wire it up (R15.6, R15.8, R15.10)

In both environments:

- `modules/artifact-repo`: add `readers`, a repository-level `roles/artifactregistry.reader`, and pass the node SA.
- Add `module.batch_cluster.workload_service_accounts["reports"]` to the db module's `secret_readers`.

## Review

Dev: **9 to add, 0 to change, 0 to destroy**. Which of the 9 is the cluster, and which
four are about *identity*?

## Reflection questions

1. Why is the pod range so much bigger than the node range?
2. A developer runs `kubectl` from their laptop. What fails, and what's the supported path?
3. A pod in namespace `default` with KSA `report-generator` tries to read the DB secret. Does it work? Why not?
4. Why grant `artifactregistry.reader` on the repository rather than at project level?
