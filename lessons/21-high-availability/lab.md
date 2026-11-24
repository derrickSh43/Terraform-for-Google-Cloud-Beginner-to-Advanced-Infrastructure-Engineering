# Lesson 21 Lab — Survive the loss of any zone

```powershell
python course.py start 21
python course.py check 21
```

The starter is the lesson 20 solution plus an empty `modules/internal-lb` and `state/dev.tfstate`
(dev after lesson 20). Guard rail: R21.9 (only the old app VM's own pieces may be deleted in dev).

Before changing anything, list the single points of failure yourself: for each tier in dev and prod,
which zone(s) does it run in, and what happens if that zone goes down?

---

## Part A — The app tier becomes a regional MIG (R21.1, R21.8, R21.9)

1. `modules/mig-service`:
   - add `writable_buckets` (list, default `[]`) and `google_storage_bucket_iam_member.writer`,
     exactly as in `vm-service` (same address and `for_each`, so the backups grant is kept);
   - set `distribution_policy_target_shape = "EVEN"` on the MIG.
2. In both environments, change `module "app"` to `source = "../../modules/mig-service"`: replace
   `zone` with `region` + `zones = var.app_zones`, drop the data-disk inputs, and set `port = 8080`,
   `health_check_path = "/health.json"`, `min_replicas = var.app_min_replicas`, `max_replicas = var.app_max_replicas`.
3. Declare `app_zones`, `app_min_replicas`, `app_max_replicas`. dev: 2 zones, 2–3 VMs. prod: 3 zones, 3–6 VMs.
   Remove `output "app_internal_ip"` from both environments for now: a fleet has no single internal IP, and
   `mig-service` has no such output. Part B brings it back.
4. Run the check and read the dev plan. **Is the data disk going to be deleted, despite `prevent_destroy`?**
   Why?
5. Add `envs/dev/decommission.tf` with a `removed` block for `module.app.google_compute_disk.data`
   (`destroy = false`). The plan now shows the disk as *forget*.

## Part B — An internal load balancer (R21.2 – R21.4)

1. `modules/internal-lb` (inputs `name`, `region`, `network_id`, `subnet_id`, `instance_group`, `port`, `health_check_path`):
   - `google_compute_region_health_check` (HTTP on `port`, 5 s interval, 2 failures);
   - `google_compute_region_backend_service`: `load_balancing_scheme = "INTERNAL"`, `protocol = "TCP"`,
     one `backend` with `group = var.instance_group` and `balancing_mode = "CONNECTION"`;
   - `google_compute_forwarding_rule`: `INTERNAL`, `ports = [tostring(var.port)]`, in `var.subnet_id`;
   - output `ip_address`.
2. Call it as `module "app_lb"` in both environments with `instance_group = module.app.instance_group`.
3. Firewall: allow `130.211.0.0/22` and `35.191.0.0/16` to tag `app` on **8080**.
4. Put `output "app_internal_ip"` back in both environments. It now returns `module.app_lb.ip_address`.

## Part C — Size prod for a zone loss (R21.5 – R21.7)

1. Prod web: the business needs **4** web VMs and **2** app VMs serving at all times. Work out the
   minimum with the table in the README. (Hint: 4 web VMs over 3 zones is not enough.)
2. Check that prod has no single point of failure left. The check names any it finds and the zone that kills it.

## Review

Dev: **8 to add, 1 to change, 4 to destroy** (and the disk forgotten). Prod: no single point of failure.
Dev still has one, the zonal database: that's a decision, not an accident. Write it down where your team will see it.

## Reflection questions

1. Prod's app tier has 3 VMs over 3 zones. A zone fails during a deploy that is replacing VMs (`max_unavailable_fixed = 0`). How many app VMs serve traffic at the worst moment?
2. Cloud SQL REGIONAL fails over in about a minute. What do the app VMs see during that minute, and what should they do?
3. Why does `prevent_destroy` not protect a resource whose block you delete? Is that a bug?
4. The internal LB health check passes, but `/health.json` is a static file. What failure would it miss? What would a better health endpoint check, and what's the risk if it checks too much?
5. You lose a whole region, not a zone. Which parts of Meridian survive? (Lesson 22.)
