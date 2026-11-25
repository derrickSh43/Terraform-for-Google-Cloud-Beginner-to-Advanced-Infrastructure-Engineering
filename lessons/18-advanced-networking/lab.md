# Lesson 18 Lab — A hybrid network hub

```powershell
python course.py start 18
python course.py check 18
```

The starter is the lesson 17 solution plus a new root, `envs/hub` (versions, backend,
variables and tfvars ready; `providers.tf` has only the default provider; `main.tf` is a TODO),
an empty `modules/ha-vpn`, and `state/dev.tfstate` (dev after lesson 17).

---

## Part A — Two projects, one configuration (R18.1)

1. In `envs/hub/providers.tf`, add a second `provider "google"` with `alias = "onprem"` and
   `project = var.onprem_project_id`.
2. Small helper modules (write them, with descriptions):
   - `modules/project-apis`: `google_project_service` for each of `var.apis`
   - `modules/peering-half`: one `google_compute_network_peering` with `import_custom_routes` / `export_custom_routes` variables
3. In `envs/hub/main.tf`: enable `compute` + `dns` in the hub, and `compute` in on-prem
   (`providers = { google = google.onprem }`). Then **reuse `modules/network` twice**:
   `hub_network` (`meridian-hub`, `var.hub_subnets`) and `onprem_network`
   (`meridian-onprem-sim`, `var.onprem_subnets`, **with the alias**).

## Part B — HA VPN with BGP (R18.2 – R18.5)

`modules/ha-vpn` needs a `versions.tf` with `configuration_aliases = [google.peer]`. Inputs: `name`, `region`,
`network_id`, `peer_network_id`, `local_asn` and `peer_asn`, plus `advertised_ranges` (default `[]`) and `link_ranges`
(default `["169.254.0.0/30", "169.254.0.4/30"]`). Name each pair of resources `local` and `peer`. Then:

1. One `google_compute_ha_vpn_gateway` per side (`provider = google.peer` on the peer side).
2. One `google_compute_router` per side: the local one with `bgp { asn = var.local_asn  advertise_mode = "CUSTOM"
   advertised_groups = ["ALL_SUBNETS"] }` plus a `dynamic "advertised_ip_ranges"` over `var.advertised_ranges`;
   the peer one with `asn = var.peer_asn`.
3. `random_password` (`count = 2`, 32 characters) for the pre-shared keys.
4. Tunnels, `count = 2` per side: `vpn_gateway_interface = count.index`, `peer_gcp_gateway` = the
   other side's gateway, `shared_secret = random_password.psk[count.index].result`, `router`.
5. Per side and tunnel: `google_compute_router_interface` (`ip_range` `.1/30` here, `.2/30` there, from
   `var.link_ranges`; use `cidrhost`) and `google_compute_router_peer` (`peer_ip_address` = the other side's
   address, `peer_asn` = the other side's ASN).

Call it from the hub with `providers = { google = google, google.peer = google.onprem }`, ASNs
64514 / 64515, and `advertised_ranges = var.spoke_ranges`.

## Part C — Shared VPC and DNS (R18.7, R18.8)

1. `modules/shared-vpc`: `google_compute_shared_vpc_host_project`, a
   `google_compute_shared_vpc_service_project` per service project, and
   `google_compute_subnetwork_iam_member` (`roles/compute.networkUser`) on **the named subnet**.
   Attach `var.analytics_project_id` to subnet `meridian-hub-analytics` for
   `group:meridian-analytics@meridianbooks.example`.
2. `modules/dns-hybrid`: a private `google_dns_managed_zone` for `corp.meridianbooks.internal.`
   with `forwarding_config` → `var.onprem_dns_servers` (`forwarding_path = "private"`), visible to
   the hub network, and a `google_dns_policy` with `enable_inbound_forwarding = true`.

## Part D — Spokes (R18.6, R18.9, R18.10)

- Hub: `module "spoke_peering"` with `for_each = var.spoke_networks`, hub → spoke, `export_custom_routes = true`.
- dev and prod: `module "hub_peering"` (peering-half), spoke → hub (`var.hub_network_id`), `import_custom_routes = true`.

## Review

- dev: **1 to add**. hub: **33 to add**.
- In the hub plan JSON (`.course/build/18l/envs/hub/plan.json`), find
  `module.vpn.google_compute_ha_vpn_gateway.peer`. Which project will it be created in, and why?

## Reflection questions

1. Delete the `advertised_ip_ranges`. What can on-prem still reach, and what not?
2. dev is peered with both ops and the hub. Can ops reach on-prem? Why not?
3. Why must the two sides use different ASNs?
4. The analytics team asks for networkUser "on the network, it's easier". What would that give them?
