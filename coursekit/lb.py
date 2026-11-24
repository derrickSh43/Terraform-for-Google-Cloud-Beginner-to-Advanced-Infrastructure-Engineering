"""Trace Google Cloud HTTP(S) load balancers through a plan.

A global external Application Load Balancer is a chain of resources:

    forwarding rule -> target HTTP(S) proxy -> URL map -> backend service -> instance group -> VMs
                                                              \\-> health check

`trace(plan)` follows that chain via configuration references (works inside
modules) and known IDs (e.g. from a deployed state), and reports every broken
link instead of raising, so checks can show students exactly where it breaks.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .plan import Plan, Resource

PROXY_TYPES = ("google_compute_target_http_proxy", "google_compute_target_https_proxy")
GROUP_TYPES = ("google_compute_instance_group",
               "google_compute_region_instance_group_manager", "google_compute_instance_group_manager")
GOOGLE_LB_RANGES = ("130.211.0.0/22", "35.191.0.0/16")   # Google Front Ends and health checkers


@dataclass
class Backend:
    service: Resource
    groups: list[Resource] = field(default_factory=list)
    instances: list[Resource] = field(default_factory=list)
    instances_unknown: bool = False     # group membership only known after apply
    templates: list[Resource] = field(default_factory=list)   # instance templates of managed groups
    port: int | None = None             # resolved from port_name + the group's named_port
    health_checks: list[Resource] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


@dataclass
class Frontend:
    rule: Resource
    ports: str
    proxy: Resource | None = None
    url_map: Resource | None = None
    redirects_to_https: bool = False
    backends: list[Backend] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def https(self) -> bool:
        return self.proxy is not None and self.proxy.type == "google_compute_target_https_proxy"

    def serves(self, vm: Resource) -> bool:
        return any(vm.address == i.address for b in self.backends for i in b.instances)


def _links(plan: Plan, res: Resource, rtype: str, path: str) -> list[Resource]:
    found = plan.linked(res, rtype, path)
    if found:
        return found
    val = res.get(path.replace(".", ".0.") if "." in path else path)
    vals = val if isinstance(val, list) else [val]
    out = []
    for v in vals:
        r = plan.find_by_id(v) if isinstance(v, str) else None
        if r is not None and r.type == rtype:
            out.append(r)
    return out


def _backend(plan: Plan, svc: Resource) -> Backend:
    b = Backend(service=svc)
    b.health_checks = _links(plan, svc, "google_compute_health_check", "health_checks")
    if not b.health_checks:
        b.problems.append(f"{svc.address} has no health check")
    blocks = svc.blocks("backend")
    if not blocks:
        b.problems.append(f"{svc.address} has no backend block")
    b.groups = [g for t in GROUP_TYPES for g in plan.linked(svc, t, "backend.group")]
    if not b.groups:
        for blk in blocks:
            r = plan.find_by_id(blk.get("group"))
            if r is not None and r.type in GROUP_TYPES:
                b.groups.append(r)
    if not b.groups and blocks:
        # `dynamic "backend"` blocks are absent from plan JSON: fall back to the
        # instance groups handed to this module through its input variables.
        b.groups = plan.module_input_resources(svc.module, GROUP_TYPES)
    if blocks and not b.groups:
        b.problems.append(f"{svc.address} backend group is not an instance group (managed or unmanaged) in this configuration")
    port_name = svc.get("port_name", "http")
    for g in b.groups:
        named = {p.get("name"): p.get("port") for p in g.blocks("named_port")}
        if port_name not in named:
            b.problems.append(f"{g.address} has no named_port \"{port_name}\" (the backend service's port_name); "
                              f"it has {sorted(named) or 'none'}")
        else:
            b.port = int(named[port_name])
        if g.type != "google_compute_instance_group":       # managed: VMs come from a template
            b.instances_unknown = True
            b.templates += [t for t in plan.linked(g, "google_compute_instance_template", "version.instance_template")
                            if t not in b.templates]
            continue
        if g.is_unknown("instances"):
            b.instances_unknown = True
        for link in g.get("instances") or []:
            vm = plan.find_by_id(link)
            if vm is not None:
                b.instances.append(vm)
        b.instances += [vm for vm in plan.linked(g, "google_compute_instance", "instances") if vm not in b.instances]
    return b


def trace(plan: Plan) -> list[Frontend]:
    fronts = []
    for rule in plan.resources("google_compute_global_forwarding_rule"):
        proxies = [p for t in PROXY_TYPES for p in _links(plan, rule, t, "target")]
        if not proxies and rule.get("target") in ("all-apis", "vpc-sc"):
            continue                       # Private Service Connect endpoint, not a load balancer
        f = Frontend(rule=rule, ports=str(rule.get("port_range", "")))
        if not proxies:
            f.problems.append(f"{rule.address} does not point at a target HTTP(S) proxy")
            fronts.append(f)
            continue
        f.proxy = proxies[0]
        maps = _links(plan, f.proxy, "google_compute_url_map", "url_map")
        if not maps:
            f.problems.append(f"{f.proxy.address} has no URL map")
            fronts.append(f)
            continue
        f.url_map = maps[0]
        redirect = f.url_map.get("default_url_redirect.0") or {}
        if redirect.get("https_redirect") is True:
            f.redirects_to_https = True
        else:
            services = _links(plan, f.url_map, "google_compute_backend_service", "default_service")
            if not services:
                f.problems.append(f"{f.url_map.address} has no default_service backend")
            f.backends = [_backend(plan, s) for s in services]
            for b in f.backends:
                f.problems += b.problems
        fronts.append(f)
    return fronts


def http_frontends(plan: Plan) -> list[Frontend]:
    return [f for f in trace(plan) if not f.https]


def port_in_range(port: int, port_range: str) -> bool:
    if not port_range:
        return False
    if "-" in port_range:
        lo, hi = port_range.split("-", 1)
        return int(lo) <= port <= int(hi)
    return int(port_range) == port
