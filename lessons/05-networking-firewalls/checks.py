"""Lesson 05 - Cloud Networking I and Firewalls: requirement checks.

Connectivity requirements are evaluated by coursekit.firewall, an offline model
of VPC firewall semantics, in place of real `curl` / `nc` tests.
"""

import ipaddress

from coursekit.checks import one, require, requirement
from coursekit.firewall import Firewall


def _vm_by_tag(plan, tag):
    vms = plan.by_tag(tag)
    require(vms, f'No VM with the network tag "{tag}" found')
    require(len(vms) == 1, f'Expected one VM tagged "{tag}", found {len(vms)}')
    return vms[0]


def _subnet_of(plan, vm):
    subs = plan.linked(vm, "google_compute_subnetwork", "network_interface.subnetwork")
    require(len(subs) == 1, f"{vm.address} must reference exactly one subnet")
    return subs[0]


def _endpoints(plan):
    fw = Firewall(plan)
    return fw, fw.instance(_vm_by_tag(plan, "web"), "web VM"), fw.instance(_vm_by_tag(plan, "app"), "app VM")


def _expect(fw, src, dst, port, allowed, protocol="tcp"):
    v = fw.evaluate(src, dst, protocol, port)
    word = "ALLOWED" if allowed else "DENIED"
    require(v.allowed == allowed, f"{src.label} -> {dst.label}:{port}/{protocol} should be {word}, but is {'ALLOWED' if v.allowed else 'DENIED'} ({v.reason})")
    return v


# ------------------------------------------------------------------ lab
@requirement("R5.1", "A private app subnet that doesn't overlap the web subnet",
             hint='Second google_compute_subnetwork, e.g. 10.10.2.0/24, same VPC, private_ip_google_access = true')
def app_subnet(plan):
    web_sub = _subnet_of(plan, _vm_by_tag(plan, "web"))
    app_sub = _subnet_of(plan, _vm_by_tag(plan, "app"))
    require(web_sub.address != app_sub.address, "The app VM must be in its own subnet, not the web subnet")
    a = ipaddress.ip_network(app_sub.get("ip_cidr_range"), strict=False)
    w = ipaddress.ip_network(web_sub.get("ip_cidr_range"), strict=False)
    require(a.is_private, f"App subnet {a} is not a private range")
    require(not a.overlaps(w), f"App subnet {a} overlaps the web subnet {w}")
    require(app_sub.references_type("google_compute_network", "network"), "The app subnet is not in your VPC")
    require(app_sub.get("private_ip_google_access") is True, "Enable Private Google Access on the app subnet")


@requirement("R5.2", "The app VM is private and has its own identity",
             hint='tags = ["app"], no access_config, and a new google_service_account (e.g. meridian-app)')
def app_vm(plan):
    app = _vm_by_tag(plan, "app")
    web = _vm_by_tag(plan, "web")
    nic = (app.blocks("network_interface") or [{}])[0]
    require(not nic.get("access_config"), "The app VM has an external IP (access_config) - it must be internal only")
    app_sa = plan.linked(app, "google_service_account", "service_account")
    web_sa = plan.linked(web, "google_service_account", "service_account")
    require(app_sa, "The app VM does not run as one of your service accounts")
    require({s.address for s in app_sa}.isdisjoint({s.address for s in web_sa}),
            "The app VM reuses the web service account - give each workload its own identity")
    require(app.get("machine_type") in ("e2-micro", "e2-small", "e2-medium"), "Keep the app VM small (e2-micro)")


@requirement("R5.3", "Every firewall rule belongs to the Meridian VPC",
             hint="network = google_compute_network.main.id on each google_compute_firewall")
def rules_on_vpc(plan):
    rules = plan.resources("google_compute_firewall")
    require(rules, "No google_compute_firewall resources found")
    for r in rules:
        require(r.references_type("google_compute_network", "network"),
                f"{r.address} is not attached to your VPC (network = \"{r.get('network', '')}\")")


@requirement("R5.4", "Every ingress ALLOW rule targets specific instances",
             hint="Add target_tags (or target_service_accounts). A rule without targets applies to every VM in the VPC.")
def rules_targeted(plan):
    require(plan.resources("google_compute_firewall"), "No google_compute_firewall resources found")
    for r in plan.resources("google_compute_firewall"):
        if str(r.get("direction") or "INGRESS") == "INGRESS" and r.blocks("allow"):
            require(r.get("target_tags") or r.get("target_service_accounts") or r.is_unknown("target_service_accounts"),
                    f"{r.address} has no target_tags or target_service_accounts")


@requirement("R5.5", "SSH and RDP are never open to the internet",
             hint="Admin access goes through IAP: source_ranges = [\"35.235.240.0/20\"]")
def no_world_admin(plan):
    fw = Firewall(plan)
    for port in (22, 3389):
        bad = fw.rules_open_to_world(port)
        require(not bad, f"Port {port} is open to 0.0.0.0/0 via " + ", ".join(r.address for r in bad))


@requirement("R5.6", "Connectivity: internet -> web VM on port 80 is allowed",
             hint="INGRESS allow tcp:80 from 0.0.0.0/0 with target_tags = [\"web\"]")
def internet_to_web(plan):
    fw, web, _ = _endpoints(plan)
    _expect(fw, fw.internet(), web, 80, True)


@requirement("R5.7", "Connectivity: SSH only through IAP, to both tiers",
             hint="INGRESS allow tcp:22 from 35.235.240.0/20 targeting web and app")
def ssh_via_iap(plan):
    fw, web, app = _endpoints(plan)
    _expect(fw, fw.iap(), web, 22, True)
    _expect(fw, fw.iap(), app, 22, True)
    _expect(fw, fw.internet(), web, 22, False)


@requirement("R5.8", "Connectivity: web VM -> app VM on port 8080 is allowed",
             hint="INGRESS allow tcp:8080 with source_tags = [\"web\"] and target_tags = [\"app\"]")
def web_to_app(plan):
    fw, web, app = _endpoints(plan)
    _expect(fw, web, app, 8080, True)


@requirement("R5.9", "Connectivity: the app tier is otherwise unreachable",
             hint="Open only what the matrix needs - the implied deny-ingress rule blocks the rest.")
def app_isolated(plan):
    fw, web, app = _endpoints(plan)
    _expect(fw, fw.internet(), app, 8080, False)
    _expect(fw, web, app, 22, False)
    _expect(fw, web, app, 5432, False)
    _expect(fw, fw.internet(), web, 8080, False)


@requirement("R5.10", "Output exposes the app VM's internal IP",
             hint="output \"app_internal_ip\" { value = google_compute_instance.app.network_interface[0].network_ip }")
def app_output(plan):
    require("app_internal_ip" in plan.outputs(), 'output "app_internal_ip" is not defined')
    refs = plan.output_references("app_internal_ip")
    require(any(r.startswith("google_compute_instance.") for r in refs), "app_internal_ip should reference the app VM")


# ------------------------------------------------------------------ challenge
@requirement("C5.1", "Web -> app access is granted by service account, not tag",
             hint="source_service_accounts = [web SA email], target_service_accounts = [app SA email]", level="challenge")
def sa_based(plan):
    fw, web, app = _endpoints(plan)
    v = _expect(fw, web, app, 8080, True)
    addr = v.reason.split(" ", 1)[0]
    rule = plan.resource(addr)
    require(rule is not None, f"Could not identify the rule allowing web -> app ({v.reason})")
    require(rule.references_type("google_service_account", "source_service_accounts"),
            f"{addr} should use source_service_accounts (web identity)")
    require(rule.references_type("google_service_account", "target_service_accounts"),
            f"{addr} should use target_service_accounts (app identity)")
    # tag-based paths must not still allow it
    for r in plan.resources("google_compute_firewall"):
        if "app" in (r.get("target_tags") or []) and "web" in (r.get("source_tags") or []):
            require(False, f"{r.address} still allows web -> app by tag; remove it")


@requirement("C5.2", "App tier egress is locked down to Google APIs",
             hint="EGRESS deny all (priority 65000) + EGRESS allow 199.36.153.8/30 tcp:443 (priority 1000) for the app tier",
             level="challenge")
def egress_lockdown(plan):
    fw, web, app = _endpoints(plan)
    _expect(fw, app, fw.ip("203.0.113.10"), 443, False)
    _expect(fw, app, fw.ip("199.36.153.9"), 443, True)
    _expect(fw, web, fw.ip("203.0.113.10"), 443, True)
    _expect(fw, web, app, 8080, True)


@requirement("C5.3", "Firewall rule logging is enabled on every rule",
             hint='log_config { metadata = "INCLUDE_ALL_METADATA" }', level="challenge")
def fw_logging(plan):
    require(plan.resources("google_compute_firewall"), "No google_compute_firewall resources found")
    for r in plan.resources("google_compute_firewall"):
        require(r.get("log_config.0.metadata"), f"{r.address} has no log_config")


@requirement("C5.4", "Every firewall rule documents its purpose",
             hint="Set description on each google_compute_firewall.", level="challenge")
def fw_descriptions(plan):
    require(plan.resources("google_compute_firewall"), "No google_compute_firewall resources found")
    for r in plan.resources("google_compute_firewall"):
        require(r.get("description"), f"{r.address} has no description")
