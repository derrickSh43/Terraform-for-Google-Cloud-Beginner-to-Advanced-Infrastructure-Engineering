"""Lesson 09 - Autoscaling and Instance Management.

`plan` is dev against the deployed lesson 08 environment. Web VMs no longer
exist as resources: they come from an instance template, so connectivity checks
use the template as the "web VM" endpoint.
"""

from coursekit import lb
from coursekit.checks import require, requirement
from coursekit.firewall import Endpoint, Firewall

MIG_TYPES = ("google_compute_region_instance_group_manager", "google_compute_instance_group_manager")
PUBLIC_MIRROR = "151.101.2.132"


def _template(plan):
    ts = [t for t in plan.resources("google_compute_instance_template") if "web" in (t.get("tags") or [])]
    require(len(ts) == 1, f'Expected one instance template tagged "web", found {len(ts)}')
    return ts[0]


def _mig(plan):
    migs = [m for t in MIG_TYPES for m in plan.resources(t)]
    require(len(migs) == 1, f"Expected one managed instance group for the web tier, found {len(migs)}")
    return migs[0]


def _autoscaler(plan):
    scalers = plan.resources("google_compute_region_autoscaler") + plan.resources("google_compute_autoscaler")
    require(len(scalers) == 1, f"Expected one autoscaler, found {len(scalers)}")
    return scalers[0]


def _endpoints(plan):
    fw = Firewall(plan)
    apps = plan.by_tag("app")
    require(len(apps) == 1, "Expected one app VM")
    return fw, fw.instance(_template(plan), "web VM (from template)"), fw.instance(apps[0], "app VM")


def _expect(fw, src, dst, port, want):
    v = fw.evaluate(src, dst, "tcp", port)
    require(v.allowed == want, f"{src.label} -> {dst.label}:{port} should be {'ALLOWED' if want else 'DENIED'}, "
                               f"but is {'ALLOWED' if v.allowed else 'DENIED'} ({v.reason})")


# ------------------------------------------------------------------ lab
@requirement("R9.1", "An immutable, hardened instance template for the web tier",
             hint='google_compute_instance_template with name_prefix (not name), tags = ["web"], no access_config, '
                  "the web service account, Shielded VM, and lifecycle { create_before_destroy = true }")
def template(plan):
    t = _template(plan)
    nic = (t.blocks("network_interface") or [{}])[0]
    require(not nic.get("access_config"), "Template VMs must not get external IPs")
    require(t.references_type("google_service_account", "service_account") or
            plan.linked(t, "google_service_account", "service_account"),
            "The template does not run VMs as the web service account")
    sh = t.get("shielded_instance_config.0") or {}
    require(sh.get("enable_secure_boot") is True, "Enable Shielded VM secure boot on the template")
    require("nginx" in (t.get("metadata_startup_script") or "").lower(), "The template's startup script must install NGINX")
    require(t.constant("name") is None and not t.references("name"),
            "Use name_prefix, not name: templates are immutable, and a fixed name can't be replaced before it is deleted")
    found = False
    for blk in plan.source.blocks("resource", "google_compute_instance_template"):
        lc = blk.block("lifecycle")
        if lc and (lc.attr("create_before_destroy") or "").lower() == "true":
            found = True
    require(found, "The template needs lifecycle { create_before_destroy = true }")


@requirement("R9.2", "A regional MIG spreads the web tier across zones",
             hint="google_compute_region_instance_group_manager: distribution_policy_zones (>= 2), version.instance_template, "
                  'named_port { name = "http"  port = 80 }')
def mig(plan):
    m = _mig(plan)
    require(m.type == "google_compute_region_instance_group_manager",
            "Use a REGIONAL managed instance group: a zonal one dies with its zone")
    zones = m.get("distribution_policy_zones") or []
    require(len(zones) >= 2 or m.is_unknown("distribution_policy_zones"), f"The MIG spans {len(zones)} zone(s): use at least 2")
    require(plan.linked(m, "google_compute_instance_template", "version.instance_template"),
            "The MIG's version does not use your instance template")
    named = {p.get("name"): p.get("port") for p in m.blocks("named_port")}
    require(named.get("http") == 80, f'The MIG needs named_port "http" = 80 for the load balancer (has {named or "none"})')
    require(not m.get("target_size"), "Don't set target_size on an autoscaled MIG: the autoscaler owns the size")


@requirement("R9.3", "An autoscaler with sane bounds",
             hint="google_compute_region_autoscaler: target = the MIG, min_replicas >= 2, max_replicas <= 10, "
                  "cpu_utilization.target 0.5-0.8, cooldown_period >= 60")
def autoscaler(plan):
    a = _autoscaler(plan)
    require(plan.linked(a, _mig(plan).type, "target"), "The autoscaler does not target the web MIG")
    pol = a.get("autoscaling_policy.0") or {}
    mn, mx = int(pol.get("min_replicas", 0)), int(pol.get("max_replicas", 0))
    require(mn >= 2, f"min_replicas = {mn}: with one VM, any failure or rollout is an outage")
    require(mn < mx <= 10, f"max_replicas = {mx}: must exceed min ({mn}) and stay <= 10 (cost guard rail)")
    cpu = float((pol.get("cpu_utilization") or [{}])[0].get("target", 0))
    require(0.5 <= cpu <= 0.8, f"CPU target {cpu}: below 0.5 wastes money, above 0.8 leaves no headroom while new VMs boot")
    require(int(pol.get("cooldown_period", 60)) >= 60, "cooldown_period should be >= 60s (boot + startup script)")


@requirement("R9.4", "Autohealing recreates broken VMs, after a realistic boot grace period",
             hint="auto_healing_policies { health_check = <autoheal check>  initial_delay_sec = 180 }")
def autohealing(plan):
    m = _mig(plan)
    pol = m.blocks("auto_healing_policies")
    require(pol, "The MIG has no auto_healing_policies: a VM whose NGINX dies stays broken forever")
    require(plan.linked(m, "google_compute_health_check", "auto_healing_policies.health_check"),
            "auto_healing_policies does not reference a health check")
    delay = int(pol[0].get("initial_delay_sec", 300))
    require(delay >= 120, f"initial_delay_sec = {delay}: shorter than boot + apt-get + NGINX start, so new VMs are "
                          "recreated before they can ever become healthy")


@requirement("R9.5", "Rolling updates never reduce capacity",
             hint='update_policy { type = "PROACTIVE"  max_unavailable_fixed = 0  max_surge_fixed = <number of zones> }')
def rolling(plan):
    m = _mig(plan)
    up = m.get("update_policy.0") or {}
    require(up, "The MIG has no update_policy")
    require(int(up.get("max_unavailable_fixed", 1) or 0) == 0 and not up.get("max_unavailable_percent"),
            "max_unavailable must be 0: otherwise a rollout takes VMs out of service before replacements are ready")
    surge = int(up.get("max_surge_fixed") or 0)
    zones = len(m.get("distribution_policy_zones") or []) or 2
    require(surge >= zones or up.get("max_surge_percent"),
            f"max_surge_fixed = {surge}: a regional MIG needs 0 or >= its number of zones ({zones}); with max_unavailable 0 it must be > 0")


@requirement("R9.6", "The load balancer now serves the MIG, not a single VM",
             hint='instance_groups = [module.web.instance_group] into the http-lb module; backend { group = ... } for each')
def lb_serves_mig(plan):
    fronts = lb.trace(plan)
    backends = [b for f in fronts for b in f.backends]
    require(backends, "No load balancer backend found")
    problems = [p for f in fronts for p in f.problems]
    require(not problems, "Broken load balancer links:\n  " + "\n  ".join(problems))
    groups = [g for b in backends for g in b.groups]
    require(any(g.type in MIG_TYPES for g in groups), "The backend service does not use the managed instance group")
    require(not any(g.type == "google_compute_instance_group" for g in groups), "Remove the old unmanaged instance group backend")


@requirement("R9.7", "Firewalls still let the load balancer, health checks, IAP and the web tier through",
             hint="Template VMs carry the web tag, so the existing tag-based rules apply unchanged.")
def connectivity(plan):
    fw, web, app = _endpoints(plan)
    for label, ip in (("Google Front End", "35.191.0.10"), ("Google health checker", "130.211.0.10")):
        _expect(fw, Endpoint(label, "internal", ip=ip), web, 80, True)
    _expect(fw, fw.iap(), web, 22, True)
    _expect(fw, web, app, 8080, True)
    _expect(fw, fw.internet(), web, 80, False)


@requirement("R9.8", "The migration is safe: only the old web VM and its unmanaged group are removed",
             hint="Keep module \"web\" with the same service account / IAM resource names so they stay untouched.")
def safe_migration(plan):
    bad, vm_deletes = [], 0
    for r in plan.all_changes():
        if r.is_replaced:
            why = ", ".join(".".join(str(x) for x in p) for p in r.replace_paths) or "a force-new attribute"
            bad.append(f"{r.address} would be REPLACED (forced by: {why})")
        elif r.actions == ["delete"]:
            if r.type == "google_compute_instance":
                vm_deletes += 1
            elif r.type != "google_compute_instance_group":
                bad.append(f"{r.address} would be DESTROYED")
    require(not bad, "Against the deployed dev environment:\n  " + "\n  ".join(bad))
    require(vm_deletes <= 1, f"{vm_deletes} VMs would be destroyed - only the old single web VM should go")
    require(plan.by_tag("app"), "The app VM must survive the migration")


@requirement("R9.9", "Web VMs stay private but can reach the internet",
             hint="No access_config on the template; the lesson 07 NAT covers the web subnet.")
def egress(plan):
    fw, web, app = _endpoints(plan)
    require(not web.external_ip, "Template VMs would get external IPs")
    _expect(fw, web, fw.ip(PUBLIC_MIRROR), 443, True)


@requirement("R9.10", "prod runs the same design with more capacity",
             hint="prod tfvars: three zones, higher min/max replicas; same module calls as dev.")
def prod(plan):
    prod = plan.others["prod"]
    srcs = lambda p: {n: c.get("source") for n, c in p.configuration.get("root_module", {}).get("module_calls", {}).items()}
    require(srcs(plan) == srcs(prod), "dev and prod call different modules")
    def bounds(p):
        a = [x for x in p.resources("google_compute_region_autoscaler")]
        require(a, f"{p.name} has no autoscaler")
        pol = a[0].get("autoscaling_policy.0") or {}
        return int(pol.get("min_replicas", 0)), int(pol.get("max_replicas", 0))
    (dmin, dmax), (pmin, pmax) = bounds(plan), bounds(prod)
    require(pmin >= dmin and pmax >= dmax, f"prod ({pmin}-{pmax}) should have at least dev's capacity ({dmin}-{dmax})")
    zones = [z for m in prod.resources("google_compute_region_instance_group_manager") for z in (m.get("distribution_policy_zones") or [])]
    require(len(zones) >= 3, f"prod MIG spans {len(zones)} zones: use all three in the region")


# ------------------------------------------------------------------ challenge
def _policy(plan):
    return _autoscaler(plan).get("autoscaling_policy.0") or {}


@requirement("C9.1", "Scale-in is rate-limited to avoid flapping",
             hint="scale_in_control { max_scaled_in_replicas { fixed = 1 }  time_window_sec = 600 }", level="challenge")
def scale_in(plan):
    sic = (_policy(plan).get("scale_in_control") or [{}])[0]
    require(sic, "No scale_in_control: after a spike the autoscaler may drop several VMs at once")
    fixed = (sic.get("max_scaled_in_replicas") or [{}])[0].get("fixed")
    require(fixed is not None and int(fixed) <= 2, "Limit scale-in to at most 2 VMs per window")
    require(int(sic.get("time_window_sec", 0)) >= 300, "time_window_sec should be >= 300")


@requirement("C9.2", "prod pre-scales for weekday business hours; dev doesn't",
             hint='dynamic "scaling_schedules" driven by a business_hours_min_replicas variable (0 = off)', level="challenge")
def schedules(plan):
    prod_pol = plan.others["prod"].resources("google_compute_region_autoscaler")[0].get("autoscaling_policy.0") or {}
    sched = prod_pol.get("scaling_schedules") or []
    require(sched, "prod has no scaling_schedules")
    s = sched[0] if isinstance(sched, list) else next(iter(sched.values()))
    require(s.get("schedule") and s.get("time_zone"), "A schedule needs a cron schedule and an explicit time_zone")
    require(int(s.get("min_required_replicas", 0)) > int(prod_pol.get("min_replicas", 0)),
            "Business-hours minimum should exceed the normal minimum")
    require(not (_policy(plan).get("scaling_schedules")), "dev should not run a business-hours schedule")


@requirement("C9.3", "The autoscaler also follows load balancer utilization",
             hint="load_balancing_utilization { target = 0.8 } alongside cpu_utilization", level="challenge")
def lb_signal(plan):
    lbu = (_policy(plan).get("load_balancing_utilization") or [{}])[0]
    require(lbu.get("target"), "No load_balancing_utilization signal")
    require(0.5 <= float(lbu["target"]) <= 0.9, "load_balancing_utilization target should be 0.5-0.9")


@requirement("C9.4", "The MIG module rejects impossible replica bounds",
             hint="validation on max_replicas referencing var.min_replicas; tests/challenge/mig_module.tftest.hcl must pass",
             level="challenge",
             test="mig_module.tftest.hcl")
def bounds_validation(plan):
    mods = plan.configuration.get("root_module", {}).get("module_calls", {})
    require(any("min_replicas" in m.get("module", {}).get("variables", {}) for m in mods.values()),
            "No module declares min_replicas")
