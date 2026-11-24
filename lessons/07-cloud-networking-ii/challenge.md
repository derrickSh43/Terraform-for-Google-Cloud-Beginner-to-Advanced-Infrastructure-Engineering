# Lesson 07 Challenge — Tighter egress, fixed IPs, private APIs

```powershell
python course.py check 07 --challenge
```

| ID | Requirement |
|---|---|
| C7.1 | NAT should serve only subnets that need it. Add a network-module variable `nat_subnets` (a set of subnet tier names, validated against `var.subnets` keys). When it's non-empty, use `LIST_OF_SUBNETWORKS` with a `dynamic "subnetwork"` block. Environments pass `["app"]`. |
| C7.2 | A payment partner allowlists our egress IPs. Reserve **two** external `google_compute_address` resources for NAT (variable `nat_ip_count`) and switch to `MANUAL_ONLY` when the count is above zero. Output the addresses. |
| C7.3 | Add a Private Service Connect endpoint for Google APIs as a new module: a `google_compute_global_address` (`purpose = "PRIVATE_SERVICE_CONNECT"`, `address_type = "INTERNAL"`, a fixed IP **outside** every subnet) and a `google_compute_global_forwarding_rule` with `target = "all-apis"`. The rule name must be 1–20 lowercase letters/digits (`meridiandevapis`), so add a validation. |
| C7.4 | Least privilege across the peering: no custom route exchange in either direction, and the ops range reaches only port 9100 (not 22, not 8080). |

## Hints

- `name = google_compute_subnetwork.this[subnetwork.value].id` inside the dynamic block's `content`.
- `nat_ips = google_compute_address.nat[*].self_link` (a splat over a `count` resource).
- A conditional attribute: `nat_ip_allocate_option = var.nat_ip_count > 0 ? "MANUAL_ONLY" : "AUTO_ONLY"`.
- Dev PSC IP `10.10.255.250`, prod `10.20.255.250`. Inside each env's /16, outside every /24 subnet.

## Think about it

Switching the deployed NAT from `AUTO_ONLY` to `MANUAL_ONLY` changes its egress
IPs **in place**. Long-lived connections from the app VM drop. When would you
schedule that change?
