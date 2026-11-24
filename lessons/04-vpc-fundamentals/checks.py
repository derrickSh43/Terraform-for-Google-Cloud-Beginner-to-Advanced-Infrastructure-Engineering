"""Lesson 04 - VPC Fundamentals: requirement checks."""

import ipaddress
import itertools

from coursekit.checks import one, require, requirement


def _vpc(plan):
    return one(plan, "google_compute_network", "VPC network")


def _vm(plan):
    return one(plan, "google_compute_instance", "Compute Engine VM")


def _web_subnet(plan):
    """The subnet the web VM is attached to - whatever the student named it."""
    vm = _vm(plan)
    subnets = plan.linked(vm, "google_compute_subnetwork", "network_interface.subnetwork")
    require(subnets, "The web VM's network_interface does not reference a google_compute_subnetwork")
    require(len(subnets) == 1, "The VM's subnetwork reference is ambiguous - reference one subnet instance")
    return subnets[0]


# ------------------------------------------------------------------ lab
@requirement("R4.1", "A custom-mode VPC",
             hint="google_compute_network with auto_create_subnetworks = false")
def custom_vpc(plan):
    vpc = _vpc(plan)
    require(vpc.get("auto_create_subnetworks") is False,
            "auto_create_subnetworks is not false - auto mode creates a subnet in every region with fixed ranges")


@requirement("R4.2", "VPC is named for the environment, regional routing, waits for the APIs",
             hint='name = "meridian-${var.environment}-vpc", routing_mode = "REGIONAL", depends_on the APIs')
def vpc_settings(plan):
    vpc = _vpc(plan)
    name = vpc.get("name", "")
    require(name != "default", "Don't name your VPC \"default\"")
    env = plan.variable_value("environment") or ""
    require(env in name, f"VPC name '{name}' does not include the environment '{env}'")
    require(vpc.get("routing_mode", "REGIONAL") == "REGIONAL", "routing_mode should be REGIONAL for a single-region app")
    require(vpc.depends_on_type("google_project_service"), "The VPC does not depend on the Compute API being enabled")


@requirement("R4.3", "The web subnet is in the VPC and the configured region",
             hint="google_compute_subnetwork with network = google_compute_network.<name>.id and region = var.region")
def subnet_placement(plan):
    sub = _web_subnet(plan)
    require(sub.references_type("google_compute_network", "network"), "The subnet's network does not reference your VPC")
    region = plan.variable_value("region")
    require(sub.get("region") == region, f"Subnet region '{sub.get('region')}' is not var.region ('{region}')")


@requirement("R4.4", "The web subnet uses a sensible private range",
             hint="Use an RFC 1918 range sized /20 to /28, e.g. 10.10.1.0/24")
def subnet_cidr(plan):
    sub = _web_subnet(plan)
    raw = sub.get("ip_cidr_range", "")
    try:
        net = ipaddress.ip_network(raw, strict=True)
    except ValueError as exc:
        require(False, f"ip_cidr_range '{raw}' is not a valid network address: {exc}")
    require(net.is_private, f"{net} is not a private (RFC 1918) range")
    require(20 <= net.prefixlen <= 28, f"{net} is a /{net.prefixlen}; use /20 to /28 to leave room for growth")


@requirement("R4.5", "Private Google Access is enabled on the web subnet",
             hint="private_ip_google_access = true")
def pga(plan):
    require(_web_subnet(plan).get("private_ip_google_access") is True, "private_ip_google_access is not true")


@requirement("R4.6", "The web VM lives in the custom subnet, not the default network",
             hint="network_interface { subnetwork = google_compute_subnetwork.web.id  access_config {} }")
def vm_in_subnet(plan):
    vm = _vm(plan)
    nic = (vm.blocks("network_interface") or [{}])[0]
    require(nic.get("network") in (None, "") or vm.is_unknown("network_interface.0.network"),
            f"The VM still sets network = \"{nic.get('network')}\" - use subnetwork instead")
    _web_subnet(plan)
    require(nic.get("access_config"), "Keep the external IP (access_config) - lesson 5 restricts access with firewalls")


@requirement("R4.7", "Outputs expose the VPC and web subnet IDs",
             hint='output "vpc_id" and output "web_subnet_id"')
def outputs(plan):
    for name, rtype in (("vpc_id", "google_compute_network"), ("web_subnet_id", "google_compute_subnetwork")):
        require(name in plan.outputs(), f'output "{name}" is not defined')
        require(any(r.startswith(rtype + ".") for r in plan.output_references(name)), f'output "{name}" should reference a {rtype}')


# ------------------------------------------------------------------ challenge
@requirement("C4.1", "Subnets are generated from a map variable with for_each",
             hint='variable "subnets" (map(string), tier => CIDR) and for_each = var.subnets on one subnetwork resource',
             level="challenge")
def for_each_subnets(plan):
    require("subnets" in plan.variables(), 'variable "subnets" is not declared')
    subs = plan.resources("google_compute_subnetwork")
    require(any(isinstance(s.index, str) for s in subs), "Subnets are not created with for_each (no string-keyed instances found)")
    require(len(subs) >= 2, f"Expected at least two subnets (web and app), found {len(subs)}")


@requirement("C4.2", "No two subnets overlap", hint="Give each tier its own /24 inside 10.10.0.0/16.", level="challenge")
def no_overlap(plan):
    nets = [(s.address, ipaddress.ip_network(s.get("ip_cidr_range"), strict=False))
            for s in plan.resources("google_compute_subnetwork") if s.get("ip_cidr_range")]
    for (a, na), (b, nb) in itertools.combinations(nets, 2):
        require(not na.overlaps(nb), f"{a} ({na}) overlaps {b} ({nb})")


@requirement("C4.3", "VPC flow logs are enabled on every subnet",
             hint="log_config { aggregation_interval, flow_sampling, metadata }", level="challenge")
def flow_logs(plan):
    require(plan.resources("google_compute_subnetwork"), "No subnets found")
    for s in plan.resources("google_compute_subnetwork"):
        cfg = s.get("log_config.0")
        require(cfg, f"{s.address} has no log_config (flow logs)")
        require(0 < float(cfg.get("flow_sampling", 0)) <= 1, f"{s.address} flow_sampling must be between 0 and 1")


@requirement("C4.4", "Subnet map is validated (CIDRs and a mandatory web tier)",
             hint="Two validation blocks on var.subnets; tests/challenge/subnets.tftest.hcl must pass.", level="challenge")
def validated(plan):
    require("subnets" in plan.variables(), 'variable "subnets" is not declared')
