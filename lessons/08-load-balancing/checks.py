"""Lesson 08 - Load Balancing and Health Checks.

`plan` is dev against the deployed lesson 07 environment (state/dev.tfstate).
coursekit.lb traces forwarding rule -> proxy -> URL map -> backend service ->
instance group -> VM; coursekit.firewall decides whether Google's load balancer
and health-check ranges can reach the VMs.
"""

from coursekit import lb
from coursekit.checks import require, requirement
from coursekit.firewall import Endpoint, Firewall

LB_SOURCES = [("Google Front End", "35.191.0.10"), ("Google health checker", "130.211.0.10")]
PUBLIC_MIRROR = "151.101.2.132"


def _vm(plan, tag):
    vms = plan.by_tag(tag)
    require(len(vms) == 1, f'Expected one VM tagged "{tag}", found {len(vms)}')
    return vms[0]


def _frontends(plan):
    fronts = lb.trace(plan)
    require(fronts, "No load balancer found: expected a google_compute_global_forwarding_rule pointing at a target HTTP proxy")
    return fronts


def _serving(plan):
    """The (frontend, backend) pair that serves HTTP traffic to the web tier."""
    fronts = _frontends(plan)
    for f in fronts:
        for b in f.backends:
            if b.instances or b.instances_unknown:
                return f, b
    problems = [p for f in fronts for p in f.problems]
    require(False, "No load balancer path reaches any VM" + (":\n  " + "\n  ".join(problems) if problems else ""))


def _google_sources():
    return [Endpoint(label, "internal", ip=ip) for label, ip in LB_SOURCES]


def _endpoints(plan):
    fw = Firewall(plan)
    return fw, fw.instance(_vm(plan, "web"), "web VM"), fw.instance(_vm(plan, "app"), "app VM")


def _expect(fw, src, dst, port, want):
    v = fw.evaluate(src, dst, "tcp", port)
    require(v.allowed == want, f"{src.label} -> {dst.label}:{port} should be {'ALLOWED' if want else 'DENIED'}, "
                               f"but is {'ALLOWED' if v.allowed else 'DENIED'} ({v.reason})")


# ------------------------------------------------------------------ lab
@requirement("R8.1", "A reserved global IP with an HTTP forwarding rule on port 80",
             hint='google_compute_global_address + google_compute_global_forwarding_rule (port_range = "80", '
                  'load_balancing_scheme = "EXTERNAL_MANAGED", target = the HTTP proxy)')
def frontend(plan):
    fronts = _frontends(plan)
    http = [f for f in fronts if lb.port_in_range(80, f.ports)]
    require(http, "No forwarding rule listens on port 80")
    f = http[0]
    require(f.rule.get("load_balancing_scheme") == "EXTERNAL_MANAGED",
            f"load_balancing_scheme is '{f.rule.get('load_balancing_scheme')}': use EXTERNAL_MANAGED (the current global Application Load Balancer)")
    require(f.rule.references_type("google_compute_global_address", "ip_address"),
            "The forwarding rule should use a reserved google_compute_global_address, so the IP survives re-creation")
    require(f.proxy is not None, f"{f.rule.address} does not point at a target HTTP proxy")


@requirement("R8.2", "The load balancer chain is wired end to end",
             hint="proxy.url_map -> url_map.default_service -> backend_service.backend.group -> instance group")
def chain(plan):
    f, b = _serving(plan)
    require(not f.problems, "Broken links:\n  " + "\n  ".join(f.problems))
    require(b.groups, "The backend service has no instance group backend")


@requirement("R8.3", "A sensible HTTP health check is attached to the backend service",
             hint="google_compute_health_check with http_health_check { port, request_path }; timeout_sec <= check_interval_sec")
def health_check(plan):
    f, b = _serving(plan)
    require(b.health_checks, f"{b.service.address} has no health check: unhealthy VMs would keep receiving traffic")
    hc = b.health_checks[0]
    http = hc.get("http_health_check.0") or {}
    require(http, f"{hc.address} is not an HTTP health check")
    require(http.get("request_path"), "Set request_path on the HTTP health check")
    port = http.get("port")
    require(b.port is None or port in (None, b.port), f"The health check probes port {port} but traffic is served on {b.port}")
    interval, timeout = int(hc.get("check_interval_sec", 5)), int(hc.get("timeout_sec", 5))
    require(timeout <= interval, f"timeout_sec ({timeout}) must not exceed check_interval_sec ({interval})")
    require(int(hc.get("unhealthy_threshold", 2)) >= 2, "unhealthy_threshold of 1 makes a single slow response eject a VM")


@requirement("R8.4", "The backend serves the web VM on its named port",
             hint='Instance group with instances = [module.web.self_link] and named_port { name = "http"  port = 80 } matching port_name')
def serves_web(plan):
    f, b = _serving(plan)
    web = _vm(plan, "web")
    require(b.port is not None, "The backend service's port_name does not match a named_port on its instance group")
    if not b.instances_unknown:
        require(any(i.address == web.address for i in b.instances),
                f"The instance group contains {[i.address for i in b.instances] or 'no VMs'}, not the web VM")
        require(all("web" in (i.get("tags") or []) for i in b.instances), "Only web-tier VMs belong behind the storefront load balancer")


@requirement("R8.5", "Google's load balancer and health-check ranges can reach the web tier, and only the web tier",
             hint='Firewall rule: source_ranges = ["130.211.0.0/22", "35.191.0.0/16"], target_tags = ["web"], ports = ["80"]')
def lb_firewall(plan):
    fw, web, app = _endpoints(plan)
    f, b = _serving(plan)
    port = b.port or 80
    for src in _google_sources():
        _expect(fw, src, web, port, True)
        _expect(fw, src, app, port, False)
        _expect(fw, src, app, 8080, False)


@requirement("R8.6", "The web VM is no longer directly exposed",
             hint="external_ip = false on the web module, and remove the 0.0.0.0/0 port 80 rule")
def not_exposed(plan):
    fw, web, app = _endpoints(plan)
    require(not web.external_ip, "The web VM still has an external IP: users could bypass the load balancer")
    open_rules = fw.rules_open_to_world(80)
    require(not open_rules, "Port 80 is still open to 0.0.0.0/0 via " + ", ".join(r.address for r in open_rules))
    _expect(fw, fw.internet(), web, 80, False)


@requirement("R8.7", "The web VM can still install packages (egress through Cloud NAT)",
             hint="With no external IP the web VM needs the lesson 07 NAT to cover its subnet.")
def web_egress(plan):
    fw, web, app = _endpoints(plan)
    _expect(fw, web, fw.ip(PUBLIC_MIRROR), 443, True)


@requirement("R8.8", "The change to deployed dev is safe: nothing replaced, and only firewall rules deleted",
             hint="Expect adds for the load balancer, an in-place update of the web VM, and deletion of the old public rule.")
def safe_change(plan):
    bad = []
    for r in plan.all_changes():
        if r.is_replaced:
            why = ", ".join(".".join(str(x) for x in p) for p in r.replace_paths) or "a force-new attribute"
            bad.append(f"{r.address} would be REPLACED (forced by: {why})")
        elif r.actions == ["delete"] and r.type != "google_compute_firewall":
            bad.append(f"{r.address} would be DESTROYED")
    require(not bad, "Against the deployed dev environment:\n  " + "\n  ".join(bad))
    deleted = [r.address for r in plan.all_changes() if r.actions == ["delete"]]
    open_now = Firewall(plan).rules_open_to_world(80)
    require(deleted or not open_now, "The public port 80 rule should be deleted, not left in place")


@requirement("R8.9", "Outputs point users at the load balancer",
             hint='output "lb_ip" = module.lb.ip_address; web_url from the LB IP (or your domain); remove web_external_ip')
def outputs(plan):
    outs = plan.outputs()
    require("web_url" in outs, 'output "web_url" is missing')
    require("lb_ip" in outs, 'output "lb_ip" is missing')
    lb_modules = {r.module.split(".")[1] for r in plan.resources("google_compute_global_forwarding_rule") if r.module}
    refs = plan.output_references("lb_ip")
    require(any(r.startswith(f"module.{m}") for r in refs for m in lb_modules),
            f'output "lb_ip" should come from the load balancer module (refs: {refs or "none"})')
    vm_modules = {r.module.split(".")[1] for r in plan.resources("google_compute_instance") if r.module}
    url_refs = plan.output_references("web_url")
    bad = [r for r in url_refs if any(r.startswith(f"module.{m}.") for m in vm_modules)]
    require(not bad, f'web_url still points at a VM ({", ".join(bad)}): users must go through the load balancer')
    require("web_external_ip" not in outs, 'Remove output "web_external_ip": the web VM has no external IP any more')


@requirement("R8.10", "prod mirrors dev, and the other connectivity guarantees still hold",
             hint="Same module calls in prod. IAP SSH, web -> app:8080 and ops monitoring are unchanged.")
def guard_rails(plan):
    prod = plan.others["prod"]
    srcs = lambda p: {n: c.get("source") for n, c in p.configuration.get("root_module", {}).get("module_calls", {}).items()}
    require(srcs(plan) == srcs(prod), "dev and prod call different modules")
    require(plan.type_counts() == prod.type_counts(), "dev and prod would build different sets of resources")
    fw, web, app = _endpoints(plan)
    _expect(fw, fw.iap(), web, 22, True)
    _expect(fw, fw.iap(), app, 22, True)
    _expect(fw, web, app, 8080, True)
    _expect(fw, fw.internet(), app, 8080, False)
    _expect(fw, fw.internal_ip("10.110.0.10", "ops monitoring"), web, 9100, True)


# ------------------------------------------------------------------ challenge
@requirement("C8.1", "HTTPS on port 443 with a Google-managed certificate, on the same IP",
             hint="google_compute_managed_ssl_certificate + google_compute_target_https_proxy + a second forwarding rule (port 443) using the same address",
             level="challenge")
def https(plan):
    fronts = _frontends(plan)
    https = [f for f in fronts if f.https and lb.port_in_range(443, f.ports)]
    require(https, "No HTTPS forwarding rule on port 443")
    f = https[0]
    require(f.proxy.references_type("google_compute_managed_ssl_certificate", "ssl_certificates"),
            "The HTTPS proxy does not use a google_compute_managed_ssl_certificate")
    certs = plan.resources("google_compute_managed_ssl_certificate")
    require(certs and certs[0].get("managed.0.domains"), "The managed certificate lists no domains")
    http = [x for x in fronts if lb.port_in_range(80, x.ports)]
    require(http and set(http[0].rule.references("ip_address")) == set(f.rule.references("ip_address")),
            "HTTP and HTTPS should share one reserved IP (one DNS record)")
    require(f.backends and f.backends[0].instances or (f.backends and f.backends[0].instances_unknown),
            "HTTPS traffic does not reach the web backend")


@requirement("C8.2", "Port 80 redirects to HTTPS instead of serving the site",
             hint="A second URL map with default_url_redirect { https_redirect = true } used by the HTTP proxy",
             level="challenge")
def redirect(plan):
    http = [f for f in _frontends(plan) if lb.port_in_range(80, f.ports)]
    require(http, "No port 80 frontend")
    require(http[0].redirects_to_https, "Port 80 still serves the site in plain HTTP: redirect it to HTTPS")


@requirement("C8.3", "The backend logs requests and drains connections",
             hint="backend service: log_config { enable = true  sample_rate = 0.5 } and connection_draining_timeout_sec = 30 (10-60)",
             level="challenge")
def backend_ops(plan):
    f, b = _serving(plan)
    log = b.service.get("log_config.0") or {}
    require(log.get("enable") is True, "Backend request logging is off")
    require(0 < float(log.get("sample_rate", 0)) <= 1, "Set a log sample_rate between 0 and 1")
    drain = int(b.service.get("connection_draining_timeout_sec", 300))
    require(10 <= drain <= 60, f"connection_draining_timeout_sec is {drain}s: set it explicitly to 10-60s "
                               "(long enough for in-flight requests, short enough that the default 300s doesn't slow every rollout)")


@requirement("C8.4", "HTTPS is a module option, proven by a module test",
             hint="variables enable_https and domains on modules/http-lb; tests/challenge/http_lb_module.tftest.hcl must pass",
             level="challenge")
def module_option(plan):
    mods = plan.configuration.get("root_module", {}).get("module_calls", {})
    lb_mods = [m for m in mods.values() if "enable_https" in m.get("module", {}).get("variables", {})]
    require(lb_mods, "No module declares an enable_https variable")
