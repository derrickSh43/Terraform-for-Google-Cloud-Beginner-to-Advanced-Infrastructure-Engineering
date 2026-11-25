"""Lesson 18 - Advanced GCP Networking.

`plan` is dev against the deployed lesson 17 environment; plan.others["hub"] is
the new network hub root, which manages two projects through provider aliases.
"""

import ipaddress
import itertools

from coursekit.checks import require, requirement

LINK_LOCAL = ipaddress.ip_network("169.254.0.0/16")


def _hub(plan):
    return plan.others["hub"]


def _projects(hub):
    return hub.variable_value("hub_project_id"), hub.variable_value("onprem_project_id")


def _by_project(hub, rtype, project):
    return [r for r in hub.resources(rtype) if r.get("project") == project]


def _private_asn(a):
    return 64512 <= a <= 65534 or 4200000000 <= a <= 4294967294


def _bgp_routers(hub):
    return [r for r in hub.resources("google_compute_router") if (r.get("bgp") or [{}])[0].get("asn")]


def _all_ranges(p, label):
    out = []
    for s in p.resources("google_compute_subnetwork"):
        if s.get("ip_cidr_range"):
            out.append((f"{label} subnet {s.get('name')}", ipaddress.ip_network(s.get("ip_cidr_range"), strict=False)))
        for r in s.get("secondary_ip_range") or []:
            out.append((f"{label} {s.get('name')}/{r.get('range_name')}", ipaddress.ip_network(r.get("ip_cidr_range"), strict=False)))
    for a in p.resources("google_compute_global_address"):
        if a.get("purpose") == "VPC_PEERING" and a.get("address"):
            out.append((f"{label} PSA", ipaddress.ip_network(f"{a.get('address')}/{a.get('prefix_length')}", strict=False)))
    return out


def _peerings_to(p, needle):
    return [x for x in p.resources("google_compute_network_peering") if needle in str(x.get("peer_network") or "")]


# ------------------------------------------------------------------ lab
@requirement("R18.1", "The hub root manages two projects with an aliased provider",
             hint='provider "google" { alias = "onprem"  project = var.onprem_project_id }; providers = { google = google.onprem } on the on-prem modules')
def providers(plan):
    hub = _hub(plan)
    cfg = hub.configuration.get("provider_config", {})
    require("google.onprem" in cfg, f"No aliased provider google.onprem (configured: {sorted(cfg)})")
    require("var.onprem_project_id" in hub.provider_references("google.onprem", "project"),
            "google.onprem should set project = var.onprem_project_id")
    hub_p, onprem_p = _projects(hub)
    require(_by_project(hub, "google_compute_network", hub_p), "No VPC in the hub project")
    require(_by_project(hub, "google_compute_network", onprem_p), "No VPC in the on-prem project - is the on-prem module using the alias?")


@requirement("R18.2", "HA VPN: a gateway on each side, two tunnels each, on both interfaces",
             hint="google_compute_ha_vpn_gateway per side; google_compute_vpn_tunnel with vpn_gateway_interface 0 and 1, peer_gcp_gateway = the other gateway")
def ha_vpn(plan):
    hub = _hub(plan)
    hub_p, onprem_p = _projects(hub)
    gws = hub.resources("google_compute_ha_vpn_gateway")
    require(len(gws) == 2 and {g.get("project") for g in gws} == {hub_p, onprem_p},
            f"Expected one HA VPN gateway in each project, found {[(g.address, g.get('project')) for g in gws]}")
    tunnels = hub.resources("google_compute_vpn_tunnel")
    require(len(tunnels) == 4, f"Expected 4 tunnels (2 per side) for the 99.99% SLA, found {len(tunnels)}")
    for gw in gws:
        mine = [t for t in tunnels if any(x.address == gw.address for x in hub.linked(t, "google_compute_ha_vpn_gateway", "vpn_gateway"))]
        ifaces = sorted(int(t.get("vpn_gateway_interface", -1)) for t in mine)
        require(ifaces == [0, 1], f"{gw.address}: tunnels use interfaces {ifaces}, need [0, 1] - one tunnel per gateway interface")
        for t in mine:
            peers = hub.linked(t, "google_compute_ha_vpn_gateway", "peer_gcp_gateway")
            require(peers and peers[0].address != gw.address, f"{t.address} must point peer_gcp_gateway at the OTHER side's gateway")


@requirement("R18.3", "BGP: distinct private ASNs, link-local sessions that match up",
             hint="Routers with ASNs 64514 / 64515; interfaces <link>.1/30 and <link>.2/30 in 169.254.0.0/16; each peer_ip_address is the other side's interface IP")
def bgp(plan):
    hub = _hub(plan)
    routers = _bgp_routers(hub)
    require(len(routers) == 2, f"Expected two BGP routers (one per side), found {len(routers)}")
    asns = [int(r.get("bgp.0.asn")) for r in routers]
    require(len(set(asns)) == 2, f"Both routers use ASN {asns[0]} - BGP needs a different ASN per side")
    require(all(_private_asn(a) for a in asns), f"Use private ASNs (64512-65534), got {asns}")
    ifaces = hub.resources("google_compute_router_interface")
    peers = hub.resources("google_compute_router_peer")
    require(len(ifaces) == 4 and len(peers) == 4, f"Expected 4 router interfaces and 4 BGP peers, found {len(ifaces)} / {len(peers)}")
    iface_ips = {}
    for i in ifaces:
        net = ipaddress.ip_interface(i.get("ip_range"))
        require(net.network.prefixlen == 30 and net.network.subnet_of(LINK_LOCAL), f"{i.address} ip_range {i.get('ip_range')}: use a /30 in 169.254.0.0/16")
        iface_ips[str(net.ip)] = i.get("project")
    links = {ipaddress.ip_interface(i.get("ip_range")).network for i in ifaces}
    require(len(links) == 2, f"Use one /30 per tunnel pair: found {sorted(map(str, links))}")
    asn_by_project = {r.get("project"): int(r.get("bgp.0.asn")) for r in routers}
    for p in peers:
        ip = p.get("peer_ip_address")
        require(ip in iface_ips and iface_ips[ip] != p.get("project"),
                f"{p.address} peers with {ip}, which is not an interface on the other side")
        other = [a for proj, a in asn_by_project.items() if proj != p.get("project")]
        require(other and int(p.get("peer_asn") or 0) == other[0], f"{p.address} peer_asn {p.get('peer_asn')} is not the other router's ASN {other}")


@requirement("R18.4", "Tunnel secrets are generated, never typed",
             hint="random_password (length >= 20) -> shared_secret on every tunnel")
def secrets(plan):
    hub = _hub(plan)
    for t in hub.resources("google_compute_vpn_tunnel"):
        require(t.constant("shared_secret") is None, f"{t.address} has a hard-coded shared_secret")
        require(t.references_type("random_password", "shared_secret"), f"{t.address} shared_secret does not come from random_password")
    pws = hub.resources("random_password")
    require(pws and all(int(p.get("length") or 0) >= 20 for p in pws), "Generate pre-shared keys of at least 20 characters")


@requirement("R18.5", "The hub announces its subnets and the spokes to on-prem",
             hint='hub router bgp: advertise_mode = "CUSTOM", advertised_groups = ["ALL_SUBNETS"], advertised_ip_ranges for 10.10.0.0/16 and 10.20.0.0/16')
def advertisement(plan):
    hub = _hub(plan)
    hub_p, _ = _projects(hub)
    r = [x for x in _bgp_routers(hub) if x.get("project") == hub_p]
    require(r, "No BGP router in the hub project")
    bgp = (r[0].get("bgp") or [{}])[0]
    require(bgp.get("advertise_mode") == "CUSTOM", "Use advertise_mode CUSTOM - the default only announces the hub's own subnets")
    require("ALL_SUBNETS" in (bgp.get("advertised_groups") or []), "Keep advertising ALL_SUBNETS")
    ranges = [ipaddress.ip_network(x.get("range"), strict=False) for x in bgp.get("advertised_ip_ranges") or []]
    for env, p in (("dev", plan), ("prod", plan.others["prod"])):
        for s in p.resources("google_compute_subnetwork"):
            if "-ops-" in str(s.get("name")):
                continue  # ops VPCs aren't connected to the hub
            net = ipaddress.ip_network(s.get("ip_cidr_range"), strict=False)
            require(any(net.subnet_of(a) for a in ranges), f"{env} subnet {s.get('name')} ({net}) isn't announced to on-prem")


@requirement("R18.6", "Hub-and-spoke peering carries on-prem routes to the spokes",
             hint="hub -> dev/prod peerings with export_custom_routes = true; dev/prod -> hub with import_custom_routes = true")
def peering(plan):
    hub = _hub(plan)
    hub_p, _ = _projects(hub)
    hub_nets = _by_project(hub, "google_compute_network", hub_p)
    require(hub_nets, "No hub VPC")
    hub_name = hub_nets[0].get("name")
    for env, p in (("dev", plan), ("prod", plan.others["prod"])):
        spoke = _peerings_to(p, f"/networks/{hub_name}")
        require(spoke, f"{env} has no peering to the hub network {hub_name}")
        require(spoke[0].get("import_custom_routes") is True, f"{env} -> hub peering must import custom routes (the on-prem routes)")
        require(hub_p in str(spoke[0].get("peer_network")), f"{env} peers with {spoke[0].get('peer_network')}, not the hub project")
        nets = p.resources("google_compute_network")
        main = [n for n in nets if "-ops-" not in str(n.get("name"))]
        back = [x for x in hub.resources("google_compute_network_peering")
                if main and str(x.get("peer_network")).endswith(f"/networks/{main[0].get('name')}")]
        require(back, f"The hub has no peering back to the {env} VPC - a peering is only ACTIVE with both halves")
        require(back[0].get("export_custom_routes") is True, f"hub -> {env} peering must export custom routes")


@requirement("R18.7", "Shared VPC: analytics uses one hub subnet, nothing more",
             hint="google_compute_shared_vpc_host_project + _service_project; google_compute_subnetwork_iam_member roles/compute.networkUser on the analytics subnet")
def shared_vpc(plan):
    hub = _hub(plan)
    hub_p, _ = _projects(hub)
    hosts = hub.resources("google_compute_shared_vpc_host_project")
    require(hosts and hosts[0].get("project") == hub_p, "The hub project is not a Shared VPC host")
    svc = hub.resources("google_compute_shared_vpc_service_project")
    analytics = hub.variable_value("analytics_project_id")
    require(any(s.get("service_project") == analytics for s in svc), f"{analytics} is not attached as a service project")
    subnet_users = [m for m in hub.resources("google_compute_subnetwork_iam_member") if m.get("role") == "roles/compute.networkUser"]
    require(subnet_users, "No subnet-level networkUser grant")
    names = {s.get("name") for s in hub.resources("google_compute_subnetwork")}
    require(all(m.get("subnetwork") in names for m in subnet_users), "networkUser should be granted on a hub subnet managed here")
    proj = [m.address for m in hub.resources("google_project_iam_member") if m.get("role") == "roles/compute.networkUser"]
    require(not proj, f"Project-level networkUser lets the service project use EVERY hub subnet: {proj}")


@requirement("R18.8", "Hybrid DNS: corp names forward to on-prem; on-prem can query the hub",
             hint="private google_dns_managed_zone with forwarding_config (target = on-prem DNS IP, forwarding_path private) + google_dns_policy enable_inbound_forwarding")
def dns(plan):
    hub = _hub(plan)
    _, onprem_p = _projects(hub)
    onprem_nets = [ipaddress.ip_network(s.get("ip_cidr_range"), strict=False) for s in _by_project(hub, "google_compute_subnetwork", onprem_p)]
    zones = [z for z in hub.resources("google_dns_managed_zone") if z.get("forwarding_config")]
    require(zones, "No DNS forwarding zone")
    z = zones[0]
    require(z.get("visibility") == "private", "The forwarding zone must be private")
    targets = (z.get("forwarding_config.0") or {}).get("target_name_servers") or []
    require(targets, "The forwarding zone has no target name servers")
    for t in targets:
        ip = ipaddress.ip_address(t.get("ipv4_address"))
        require(any(ip in n for n in onprem_nets), f"DNS target {ip} is not inside the on-prem network")
        require(t.get("forwarding_path") == "private", f"Forward to {ip} over the VPN (forwarding_path = \"private\")")
    pols = [p for p in hub.resources("google_dns_policy") if p.get("enable_inbound_forwarding") is True]
    require(pols, "No inbound DNS forwarding policy - on-prem can't resolve Google Cloud private names")


@requirement("R18.9", "No address range overlaps anywhere in the hybrid network",
             hint="hub 10.200.0.0/16, on-prem 192.168.10.0/24, dev 10.10/10.11, prod 10.20/10.21 - check every subnet, secondary and PSA range")
def no_overlap(plan):
    hub_ranges = _all_ranges(_hub(plan), "hub")
    require(len(hub_ranges) >= 2, "The hub root has no hub and on-prem subnets yet")
    ranges = _all_ranges(plan, "dev") + _all_ranges(plan.others["prod"], "prod") + hub_ranges
    for (a, na), (b, nb) in itertools.combinations(ranges, 2):
        if a.split()[0] == b.split()[0] and ("-ops-" in a or "-ops-" in b):
            continue
        require(not na.overlaps(nb), f"{a} ({na}) overlaps {b} ({nb})")


@requirement("R18.10", "Deployed dev changes safely: additions only",
             hint="dev only gains its hub peering.")
def safe(plan):
    bad = [f"{r.address} would be {'REPLACED' if r.is_replaced else 'DESTROYED'}" for r in plan.all_changes()
           if r.is_replaced or r.actions == ["delete"]]
    require(not bad, "Against the deployed dev environment:\n  " + "\n  ".join(bad))


# ------------------------------------------------------------------ challenge
@requirement("C18.1", "Spokes resolve corp names through the hub (DNS peering)",
             hint="In dev and prod: a private zone for corp.meridianbooks.internal with peering_config target_network = the hub VPC", level="challenge")
def dns_peering(plan):
    for env, p in (("dev", plan), ("prod", plan.others["prod"])):
        z = [x for x in p.resources("google_dns_managed_zone") if x.get("peering_config")]
        require(z, f"{env} has no DNS peering zone")
        tgt = (z[0].get("peering_config.0.target_network.0") or {}).get("network_url") or ""
        require("meridian-hub" in tgt, f"{env} DNS peering targets {tgt!r}, not the hub")


@requirement("C18.2", "BGP sessions are authenticated",
             hint="md5_authentication_key on every google_compute_router_peer, keys from random_password", level="challenge")
def md5(plan):
    for p in _hub(plan).resources("google_compute_router_peer"):
        require(p.blocks("md5_authentication_key"), f"{p.address} has no MD5 authentication")


@requirement("C18.3", "The hub routes globally",
             hint='routing_mode = "GLOBAL" on the hub VPC (add a routing_mode variable to the network module)', level="challenge")
def global_routing(plan):
    hub = _hub(plan)
    hub_p, _ = _projects(hub)
    nets = _by_project(hub, "google_compute_network", hub_p)
    require(nets and nets[0].get("routing_mode") == "GLOBAL", "The hub VPC uses REGIONAL routing - VPN routes wouldn't reach other regions")


@requirement("C18.4", "The VPN module rejects bad link ranges",
             hint="validation on link_ranges; tests/challenge/ha_vpn_module.tftest.hcl must pass", level="challenge",
             test="ha_vpn_module.tftest.hcl")
def link_validation(plan):
    mods = _hub(plan).configuration.get("root_module", {}).get("module_calls", {})
    require(any("link_ranges" in m.get("module", {}).get("variables", {}) for m in mods.values()), "No module declares link_ranges")
