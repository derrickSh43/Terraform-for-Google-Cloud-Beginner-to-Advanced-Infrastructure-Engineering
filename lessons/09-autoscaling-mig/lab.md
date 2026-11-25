# Lesson 09 Lab — From one VM to a self-healing fleet

```powershell
python course.py start 09
python course.py check 09
```

The starter is the lesson 08 solution, plus `modules/mig-service/main.tf`
(empty) and `state/dev.tfstate` (dev as deployed after lesson 08). R9.8 is a
guard rail and already passes. Keep it green.

**Contract:** the template's VMs carry the network tag `web`, and the MIG's named port is `http` = 80.

---

## Part A — The `mig-service` module

Nothing checks this part yet: the module does nothing until an environment calls it. Part B does that,
and checks R9.1 – R9.5 then.

### Step 1: identity first, unchanged

Copy `google_service_account.this` and `google_project_iam_member.this` from
`modules/vm-service/main.tf` into `modules/mig-service/main.tf` **unchanged**:
same resource names, same arguments. That's what keeps the deployed account
and its grants untouched (R9.8).

### Step 2: the template (R9.1)

`google_compute_instance_template` `this` with:

- `name_prefix = "meridian-${var.name}-"` (no `name`) and `lifecycle { create_before_destroy = true }`
- `tags = [var.name]`, labels with `role`
- a boot `disk` (`source_image = "debian-cloud/debian-12"`, 10 GB `pd-balanced`, `auto_delete = true`)
- `network_interface { subnetwork = var.subnet_id }` with **no** `access_config`
- OS Login metadata, `metadata_startup_script = var.startup_script`, the service account, Shielded VM

### Step 3: autohealing check, MIG and autoscaler (R9.2 – R9.5)

1. `google_compute_health_check` `autoheal`: HTTP on `var.port`, interval 15 s, unhealthy threshold 4.
2. `google_compute_region_instance_group_manager` `this`:
   `region`, `distribution_policy_zones = var.zones`, `base_instance_name`,
   `version { instance_template = google_compute_instance_template.this.id }`,
   `named_port { name = "http"  port = var.port }`,
   `auto_healing_policies { health_check = ...autoheal.id  initial_delay_sec = 180 }`,
   and an `update_policy` with `max_unavailable_fixed = 0`, `max_surge_fixed = length(var.zones)`.
   Don't set `target_size`: the autoscaler owns it.
3. `google_compute_region_autoscaler` `this`: `target` = the MIG, `min_replicas` 2,
   `max_replicas` 4, `cooldown_period` 90, `cpu_utilization { target = 0.6 }`.

Inputs without a default: `name`, `display_name`, `description`, `project_id`, `region`, `zones`, `subnet_id`,
`startup_script`, `labels`. Give every other variable a default (`port` 80, `health_check_path` `"/"`, the replica counts).

Variables need descriptions. Outputs: `service_account_email`, `instance_group`
(`google_compute_region_instance_group_manager.this.instance_group`), `template_id`.

## Part B — Rewire the environment (R9.1 – R9.9)

### Step 4: switch module "web" to the new module

Keep the module **name** `web`. Change its `source` to `../../modules/mig-service`,
replace `zone` with `region` and `zones = var.web_zones`, and pass
`min_replicas` / `max_replicas` from new env variables. Values in tfvars:

| | `web_zones` | min | max |
|---|---|---|---|
| dev | `us-central1-a`, `us-central1-b` | 2 | 4 |
| prod | `us-central1-a`, `-b`, `-c` | 3 | 6 |

### Step 5: the load balancer takes groups, not VMs

In `modules/http-lb`, replace `zone` and `instances` with `instance_groups`
(`list(string)`). Delete the unmanaged `google_compute_instance_group`. The MIG
now owns the named port. Build the backends with a dynamic block:

```hcl
dynamic "backend" {
  for_each = var.instance_groups
  content {
    group           = backend.value
    balancing_mode  = "UTILIZATION"
    max_utilization = 0.8
  }
}
```

In both environments: `instance_groups = [module.web.instance_group]`.

## Part C — Review the migration (R9.8, R9.10)

`python course.py check 09 -v`. Dev should read **4 to add, 1 to change, 2 to destroy**:

| Action | Resource | Why |
|---|---|---|
| + | autoheal check, template, MIG, autoscaler | the new fleet |
| ~ | backend service | now points at the MIG |
| − | `module.web.google_compute_instance.this` | replaced by MIG VMs |
| − | `module.lb.google_compute_instance_group.this` | replaced by the MIG |

The service account and IAM grants must **not** appear in the plan. If they
do, you renamed something in Step 1.

> **Real-world ordering:** Terraform creates and destroys in one apply, but
> GCP needs a minute or two for MIG VMs to boot and pass health checks. A zero-downtime
> production migration would do it in two applies: add the MIG as a *second*
> backend, wait until it's healthy, then remove the old VM.

## Reflection questions

1. You change the startup script. Trace exactly what happens: template, MIG, VMs, load balancer.
2. Why is `max_surge_fixed` at least the number of zones for a regional MIG?
3. CPU target 0.9 would save money. What happens during a traffic spike?
4. The autohealing check is *more* tolerant than the load balancer's. What would go wrong if it were stricter?
5. Where do the web VMs' names come from now, and why shouldn't anything depend on them?
