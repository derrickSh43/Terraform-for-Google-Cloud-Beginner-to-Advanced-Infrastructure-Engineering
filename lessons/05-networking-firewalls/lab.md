# Lesson 05 Lab — A private app tier and its firewall

```powershell
python course.py start 05
python course.py check 05
```

The starter is the lesson 04 solution plus `app.tf`, `firewall.tf` (both empty)
and `scripts/app-startup.sh` (a placeholder API on port 8080).

**Contract:** checks find VMs by their **network tags**. Tag the web VM `web`
(it already is) and the app VM `app`.

---

## Part A — The app tier (R5.1, R5.2, R5.10)

In `app.tf`:

1. `variable "app_subnet_cidr"` (default `"10.10.2.0/24"`). Put it in `variables.tf`.
2. A second `google_compute_subnetwork` in the same VPC, with Private Google Access on.
3. A new `google_service_account` (e.g. `meridian-app`) with the same two roles as
   web: `logWriter` and `metricWriter`. You can reuse `local.web_roles` in a `for_each`.
4. A `google_compute_instance` (`meridian-app-1`, e2-micro, tag `app`) in the app
   subnet with **no `access_config`**, running as the new service account, with
   the same hardening as the web VM. Use `scripts/app-startup.sh`.
5. Output `app_internal_ip` (`network_interface[0].network_ip`).

Run the check now. The connectivity requirements fail: the implied deny-ingress
rule blocks everything. That's the starting point every real VPC has.

## Part B — Open exactly what the matrix needs (R5.3 – R5.9)

Read the connectivity matrix in the [README](README.md#2-architecture-and-connectivity-matrix).
Before writing HCL, decide on paper how many rules you need and what each matches.

Every rule must:

- set `network = google_compute_network.main.id` (R5.3)
- set `direction` and `priority` explicitly, which makes them easy to read
- target specific VMs with `target_tags` (R5.4)

Rule skeleton:

```hcl
resource "google_compute_firewall" "allow_http" {
  name        = "meridian-${var.environment}-allow-http"
  description = "Public HTTP to the web tier."
  network     = google_compute_network.main.id
  direction   = "INGRESS"
  priority    = 1000

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["web"]

  allow {
    protocol = "tcp"
    ports    = ["80"]
  }
}
```

You need rules for rows 1, 3 and 4. Rows 2, 5 and 6 are handled by the implied
deny, as long as you don't open too much (R5.5, R5.9).

## Reading a failure

When a connectivity check fails, the report names the deciding rule:

```
web VM -> app VM:8080/tcp should be ALLOWED, but is DENIED (implied ingress deny rule)
```

"implied ingress deny" means *no rule of yours matched*. Check the tags, port,
direction and network. If it names one of your rules, look at that rule's
priority and action.

## Reflection questions

1. Remove `target_tags` from `allow_http`. Which VMs can now be reached on port 80? Is the app VM exposed? (Hint: does it have an external IP?)
2. A teammate adds a `deny tcp:80` rule at priority 1000, the same as your allow. Who wins?
3. Why can the web VM *reply* to internet clients when you never wrote an egress rule?
4. Why does `source_tags = ["web"]` match the web VM's *internal* IP only?
