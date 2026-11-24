"""Lesson 07 - Cloud Networking II: NAT, peering, private access.

`plan` is dev, planned against the deployed lesson 06 environment
(state/dev.tfstate), so existing resources have known IDs. New resources
(ops VPC, router, NAT, peerings) are planned. plan.others["prod"] is prod.
"""

import ipaddress
import itertools

from coursekit.checks import require, requirement
from coursekit.firewall import Firewall

PUBLIC_PACKAGE_MIRROR = "151.101.2.132"   # any public address, e.g. deb.debian.org's CDN


def _vm(plan, tag):
    vms = plan.by_tag(tag)
    require(len(vms) == 1, f'Expected one VM tagged "{tag}", found {len(vms)}')
    return vms[0]


def _main_vpc(plan):
    """The VPC the web VM lives in (resolved through deployed IDs)."""
    fw = Firewall(plan)
    net = fw.instance(_vm(plan, "web")).network
    vpc = plan.resource(net) if net else None
    require(vpc is not None and vpc.type == "google_compute_network", "Could not identify the main Meridian VPC from the web VM")
    return vpc


def _other_vpcs(plan):
    main = _main_vpc(plan)
    return [n for n in plan.resources("google_compute_network") if n.address != main.address]


def _subnets_of(plan, vpc):
    out = []
    for s in plan.resources("google_compute_subnetwork"):
        net_val = s.get("network")
        if net_val and net_val == vpc.get("id"):
            out.append(s)
        elif any(n.address == vpc.address for n in plan.linked(s, "google_compute_network", "network")):
            out.append(s)
    return out


def _net(s):
    return ipaddress.ip_network(s.get("ip_cidr_range"), strict=False)


def _key(res, attr):
    """A comparable identity for an attribute: its value if known, else its references."""
    val = res.get(attr)
    if isinstance(val, str) and val:
        return val
    return tuple(sorted(res.references(attr)))


def _module_sources(plan):
    return {name: call.get("source", "") for name, call in plan.configuration.get("root_module", {}).get("module_calls", {}).items()}


def _endpoints(plan):
    fw = Firewall(plan)
    return fw, fw.instance(_vm(plan, "web"), "web VM"), fw.instance(_vm(plan, "app"), "app VM")


def _expect(fw, src, dst, port, want):
    v = fw.evaluate(src, dst, "tcp", port)
    label = getattr(dst, "label", str(dst))
    require(v.allowed == want, f"{src.label} -> {label}:{port} should be {'ALLOWED' if want else 'DENIED'}, but is "
                               f"{'ALLOWED' if v.allowed else 'DENIED'} ({v.reason})")
    return v


def _ops_ip(plan):
    ops_subnets = [s for vpc in _other_vpcs(plan) for s in _subnets_of(plan, vpc)]
    if not ops_subnets:   # ops subnets reference an unknown network ID: anything not in the main VPC
        main_ids = {s.address for s in _subnets_of(plan, _main_vpc(plan))}
        ops_subnets = [s for s in plan.resources("google_compute_subnetwork") if s.address not in main_ids]
    require(ops_subnets, "No subnets found in the ops VPC")
    return str(_net(ops_subnets[0])[10])


# ------------------------------------------------------------------ lab
@requirement("R7.1", "A Cloud Router in the main VPC's region",
             hint="google_compute_router in the network module (count = var.enable_nat ? 1 : 0), network = the VPC, region = var.region")
def router(plan):
    main = _main_vpc(plan)
    routers = plan.resources("google_compute_router")
    require(routers, "No google_compute_router found")
    mine = [r for r in routers if any(n.address == main.address for n in plan.linked(r, "google_compute_network", "network"))
            or r.get("network") == main.get("id")]
    require(len(mine) == 1, f"Expected one router on the main VPC, found {len(mine)}")
    region = plan.variable_value("region")
    require(mine[0].get("region") == region, f"Router region is '{mine[0].get('region')}', expected '{region}'")
    require(len(routers) == 1, "Only the main VPC needs a router - the ops VPC has no NAT requirement")


@requirement("R7.2", "Cloud NAT on that router, with error logging",
             hint='google_compute_router_nat: router = google_compute_router.this[0].name, AUTO_ONLY IPs, log_config { enable = true  filter = "ERRORS_ONLY" }')
def nat(plan):
    nats = plan.resources("google_compute_router_nat")
    require(len(nats) == 1, f"Expected one google_compute_router_nat, found {len(nats)}")
    n = nats[0]
    require(plan.linked(n, "google_compute_router", "router") or n.get("router"), "The NAT does not reference the router")
    require(n.get("nat_ip_allocate_option") in ("AUTO_ONLY", "MANUAL_ONLY"), "Set nat_ip_allocate_option")
    log = (n.get("log_config") or [{}])[0]
    require(log.get("enable") is True, "NAT logging is off - you would have no record of dropped connections")
    require(log.get("filter") in ("ERRORS_ONLY", "ALL"), f"NAT log filter '{log.get('filter')}' - use ERRORS_ONLY")


@requirement("R7.3", "Connectivity: the private app VM can reach the internet through NAT",
             hint="The NAT must be in the app subnet's region and cover it (ALL_SUBNETWORKS_ALL_IP_RANGES, or list it).")
def app_egress(plan):
    fw, web, app = _endpoints(plan)
    require(not app.external_ip, "The app VM must stay private (no external IP)")
    _expect(fw, app, fw.ip(PUBLIC_PACKAGE_MIRROR), 443, True)
    _expect(fw, fw.internet(), app, 8080, False)


@requirement("R7.4", "Only the web tier has an external IP",
             hint="external_ip = true only on the web module call; NAT is for everything private.")
def only_web_public(plan):
    public = [vm for vm in plan.resources("google_compute_instance")
              if (vm.blocks("network_interface") or [{}])[0].get("access_config")]
    tags = sorted(t for vm in public for t in (vm.get("tags") or []))
    require(tags == ["web"], f"VMs with external IPs: {tags or 'none'} - expected only the web VM")


@requirement("R7.5", "An ops VPC built by reusing the network module, with non-overlapping ranges",
             hint='module "ops_network" { source = "../../modules/network"  name_prefix = "${local.name_prefix}-ops"  subnets = var.ops_subnets }')
def ops_vpc(plan):
    others = _other_vpcs(plan)
    require(len(others) == 1, f"Expected one additional (ops) VPC, found {len(others)}")
    require(others[0].get("auto_create_subnetworks") is False, "The ops VPC must be custom mode")
    sources = list(_module_sources(plan).values())
    require(sources.count("../../modules/network") >= 2,
            "The ops VPC should come from a second call of ../../modules/network, not new code")
    main_subnets = _subnets_of(plan, _main_vpc(plan))
    main_addrs = {s.address for s in main_subnets}
    for s in plan.resources("google_compute_subnetwork"):
        if s.address in main_addrs:
            continue
        for m in main_subnets:
            require(not _net(s).overlaps(_net(m)),
                    f"Subnet {s.get('name')} ({_net(s)}) overlaps main VPC subnet {m.get('name')} ({_net(m)}) - peering would be rejected")


@requirement("R7.6", "The main and ops VPCs are peered in both directions",
             hint="modules/peering: two google_compute_network_peering resources with network/peer_network swapped")
def peering(plan):
    peers = plan.resources("google_compute_network_peering")
    require(len(peers) == 2, f"Expected 2 google_compute_network_peering resources (one per side), found {len(peers)}"
                             + (" - a one-sided peering stays INACTIVE" if len(peers) == 1 else ""))
    a, b = peers
    require(_key(a, "network") == _key(b, "peer_network") and _key(a, "peer_network") == _key(b, "network"),
            "The two peerings must mirror each other (A->B and B->A)")
    require(_key(a, "network") != _key(a, "peer_network"), "A network can't peer with itself")
    main_id = _main_vpc(plan).get("id")
    if main_id:
        values = {a.get("network"), a.get("peer_network"), b.get("network"), b.get("peer_network")}
        require(main_id in values, "Neither peering connects to the main Meridian VPC")


@requirement("R7.7", "Connectivity: ops monitoring reaches node exporter (9100) on both tiers; the internet doesn't",
             hint='Firewall rule "allow-ops-monitoring": source_ranges = values(var.ops_subnets), target_tags = ["web", "app"], ports = ["9100"]')
def monitoring(plan):
    fw, web, app = _endpoints(plan)
    ops = fw.internal_ip(_ops_ip(plan), "ops monitoring")
    _expect(fw, ops, web, 9100, True)
    _expect(fw, ops, app, 9100, True)
    _expect(fw, fw.internet(), web, 9100, False)


@requirement("R7.8", "Deployed dev changes safely: nothing destroyed or replaced",
             hint="Additions only. If a resource is replaced, the report shows which attribute forces it.")
def safe_change(plan):
    bad = []
    for r in plan.all_changes():
        if r.is_replaced:
            why = ", ".join(".".join(str(x) for x in p) for p in r.replace_paths) or "a force-new attribute"
            bad.append(f"{r.address} would be REPLACED (forced by: {why})")
        elif r.actions == ["delete"]:
            bad.append(f"{r.address} would be DESTROYED")
    require(not bad, "Against the deployed dev environment:\n  " + "\n  ".join(bad))


@requirement("R7.9", "prod mirrors dev, and all four VPCs use distinct ranges",
             hint="prod tfvars: its own subnets and ops_subnets (e.g. 10.20.0.0/16 and 10.120.0.0/24).")
def prod(plan):
    prod = plan.others["prod"]
    for env, p in (("dev", plan), ("prod", prod)):
        n = len(p.resources("google_compute_network"))
        require(n == 2, f"{env} has {n} VPC(s); expected 2 (main + ops)")
    require(_module_sources(plan) == _module_sources(prod), "dev and prod call different modules")
    require(plan.type_counts() == prod.type_counts(), "dev and prod would build different sets of resources")
    nets = [(env, s.get("name"), _net(s)) for env, p in (("dev", plan), ("prod", prod))
            for s in p.resources("google_compute_subnetwork") if s.get("ip_cidr_range")]
    for (e1, n1, x), (e2, n2, y) in itertools.combinations(nets, 2):
        require(not x.overlaps(y), f"{e1} {n1} ({x}) overlaps {e2} {n2} ({y})")


@requirement("R7.10", "The lesson 05 connectivity matrix still holds",
             hint="Adding NAT and peering must not open anything new to the internet.")
def matrix(plan):
    fw, web, app = _endpoints(plan)
    for src, dst, port, want in [
        (fw.internet(), web, 80, True), (fw.internet(), web, 22, False),
        (fw.iap(), web, 22, True), (fw.iap(), app, 22, True),
        (web, app, 8080, True), (web, app, 22, False), (fw.internet(), app, 8080, False),
    ]:
        _expect(fw, src, dst, port, want)


# ------------------------------------------------------------------ challenge
def _the_nat(plan):
    nats = plan.resources("google_compute_router_nat")
    require(len(nats) == 1, "Expected exactly one Cloud NAT")
    return nats[0]


@requirement("C7.1", "NAT serves only the private app subnet",
             hint='source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS" with a subnetwork block for the app subnet only',
             level="challenge")
def nat_only_app(plan):
    n = _the_nat(plan)
    require(n.get("source_subnetwork_ip_ranges_to_nat") == "LIST_OF_SUBNETWORKS",
            f"NAT covers {n.get('source_subnetwork_ip_ranges_to_nat')} - list only the subnets that need it")
    fw, web, app = _endpoints(plan)
    listed = {e.get("name") for e in n.blocks("subnetwork")}
    require(app.subnet is not None and app.subnet.get("id") in listed, "The app subnet is not in the NAT's subnet list")
    require(web.subnet is not None and web.subnet.get("id") not in listed, "The web subnet is listed but the web VM has its own external IP")


@requirement("C7.2", "NAT egress uses two reserved, allowlistable IPs",
             hint='Two google_compute_address (EXTERNAL) + nat_ip_allocate_option = "MANUAL_ONLY" + nat_ips = google_compute_address.nat[*].self_link',
             level="challenge")
def static_ips(plan):
    n = _the_nat(plan)
    require(n.get("nat_ip_allocate_option") == "MANUAL_ONLY", "nat_ip_allocate_option must be MANUAL_ONLY")
    addrs = [a for a in plan.resources("google_compute_address") if a.get("address_type", "EXTERNAL") == "EXTERNAL"]
    require(len(addrs) >= 2, f"Reserve at least 2 external addresses for NAT, found {len(addrs)}")
    require(n.references_type("google_compute_address", "nat_ips"), "nat_ips does not reference the reserved addresses")
    region = plan.variable_value("region")
    for a in addrs:
        require(a.get("region") == region, f"{a.address} is in {a.get('region')}, not the NAT's region {region}")


@requirement("C7.3", "A Private Service Connect endpoint for Google APIs",
             hint="google_compute_global_address (PRIVATE_SERVICE_CONNECT, INTERNAL) + google_compute_global_forwarding_rule target = \"all-apis\"",
             level="challenge")
def psc(plan):
    import re
    addrs = [a for a in plan.resources("google_compute_global_address") if a.get("purpose") == "PRIVATE_SERVICE_CONNECT"]
    require(len(addrs) == 1, "Expected one global address with purpose PRIVATE_SERVICE_CONNECT")
    addr = addrs[0]
    require(addr.get("address_type") == "INTERNAL", "The PSC address must be INTERNAL")
    ip = addr.get("address")
    require(ip, "Give the PSC endpoint a fixed internal IP")
    for s in plan.resources("google_compute_subnetwork"):
        require(ipaddress.ip_address(ip) not in _net(s), f"PSC IP {ip} is inside subnet {s.get('name')} ({_net(s)})")
    rules = [r for r in plan.resources("google_compute_global_forwarding_rule") if r.get("target") == "all-apis"]
    require(len(rules) == 1, 'Expected one google_compute_global_forwarding_rule with target = "all-apis"')
    name = rules[0].get("name", "")
    require(re.fullmatch(r"[a-z][a-z0-9]{0,19}", name), f"PSC endpoint name '{name}' must be 1-20 lowercase letters/digits (no hyphens)")
    require(rules[0].references_type("google_compute_global_address", "ip_address"), "The forwarding rule should use the reserved address")


@requirement("C7.4", "The ops VPC gets only what it needs",
             hint="No custom route exchange on either peering; ops reaches 9100 only.", level="challenge")
def ops_least_privilege(plan):
    for p in plan.resources("google_compute_network_peering"):
        require(p.get("export_custom_routes") is not True and p.get("import_custom_routes") is not True,
                f"{p.address} exchanges custom routes")
    fw, web, app = _endpoints(plan)
    ops = fw.internal_ip(_ops_ip(plan), "ops monitoring")
    _expect(fw, ops, app, 8080, False)
    _expect(fw, ops, app, 22, False)
