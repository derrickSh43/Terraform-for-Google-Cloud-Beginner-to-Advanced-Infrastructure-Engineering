# Lesson 18 Challenge — Hardening the hybrid link

```powershell
python course.py check 18 --challenge
```

| ID | Requirement |
|---|---|
| C18.1 | **Spokes resolve corp names.** In dev and prod, add a private zone for `corp.meridianbooks.internal` with `peering_config { target_network { network_url = <hub VPC> } }` (a `modules/dns-peering` module). Queries from the spokes are resolved by the hub, which forwards them to on-prem. |
| C18.2 | **Authenticated BGP.** Add `md5_authentication_key` to every `google_compute_router_peer`, with keys from `random_password`. |
| C18.3 | **Global routing in the hub.** Add a `routing_mode` variable to `modules/network` (default `REGIONAL`, so dev and prod don't change) and set the hub to `GLOBAL`, so VPN-learned routes reach every region. |
| C18.4 | **The VPN module validates `link_ranges`:** exactly two **different** /30s in `169.254.0.0/16`. The lesson's test runs inside `modules/ha-vpn` with both `google` and `google.peer` mocked. |

## Think about it

- Changing `routing_mode` on the deployed dev VPC would be an in-place update. What would it change for traffic, and when would you want it?
- DNS peering vs DNS forwarding: why do the spokes use *peering* to the hub instead of forwarding straight to on-prem?
