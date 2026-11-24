"""Lesson 21 - High Availability and Fault Tolerance.

`plan` is dev against the deployed lesson 20 environment; `plan.others["prod"]` is a fresh prod.
Zone-loss requirements use coursekit.failure (remove a zone, recompute capacity).
"""

from coursekit import failure
from coursekit.checks import require, requirement
from coursekit.firewall import Firewall

HEALTH_CHECKERS = ("35.191.0.1", "130.211.0.1")
PROD_TARGETS = {"web": 4, "app": 2}          # VMs that must remain at minimum scale after any zone loss
PROD_PEAK = {"web": 6}                       # challenge: peak capacity after a zone loss
OLD_VM_PARTS = {
    "module.app.google_compute_instance.this",
    "module.app.google_compute_attached_disk.data[0]",
    "module.app.google_compute_resource_policy.snapshots[0]",
    "module.app.google_compute_disk_resource_policy_attachment.snapshots[0]",
}
DISK = "module.app.google_compute_disk.data[0]"


def _mig(plan, tier):
    migs = [m for m in plan.resources("google_compute_region_instance_group_manager") if m.module == f"module.{tier}"]
    require(migs, f"No regional MIG in module.{tier} ({plan.name})")
    return migs[0]


def _workload(plan, tier):
    addr = _mig(plan, tier).address
    return next(w for w in failure.workloads(plan) if w.address == addr)


def _ilb(plan):
    bss = [b for b in plan.resources("google_compute_region_backend_service") if b.get("load_balancing_scheme") == "INTERNAL"]
    require(bss, f"No internal regional backend service ({plan.name})")
    return bss[0]


# ------------------------------------------------------------------ lab
@requirement("R21.1", "No tier runs on a single VM: the app tier is a regional MIG with autohealing",
             hint='module "app" uses ../../modules/mig-service (same SA + IAM addresses as vm-service), zones = var.app_zones')
def app_mig(plan):
    for p in (plan, plan.others["prod"]):
        vms = [v.address for v in p.resources("google_compute_instance")]
        require(not vms, f"{p.name} still has standalone VMs: {vms}")
        mig = _mig(p, "app")
        heal = (mig.blocks("auto_healing_policies") or [{}])[0]
        require(heal.get("health_check") or mig.is_unknown("auto_healing_policies.0.health_check") or mig.is_unknown("auto_healing_policies"),
                f"{p.name}: the app MIG has no autohealing health check")


@requirement("R21.2", "An internal load balancer with a health check fronts the app MIG",
             hint="google_compute_region_health_check -> google_compute_region_backend_service (INTERNAL, backend group = module.app.instance_group) -> google_compute_forwarding_rule (INTERNAL, port 8080, app subnet)")
def ilb(plan):
    for p in (plan, plan.others["prod"]):
        bs = _ilb(p)
        require(bs.references_type("google_compute_region_health_check", "health_checks") or
                p.linked(bs, "google_compute_region_health_check", "health_checks"),
                f"{p.name}: the internal backend service has no regional health check")
        groups = p.linked(bs, "google_compute_region_instance_group_manager", "backend.group")
        require(any(g.module == "module.app" for g in groups),
                f"{p.name}: the internal backend service's backend isn't the app MIG's instance group")
        rules = [r for r in p.resources("google_compute_forwarding_rule") if r.get("load_balancing_scheme") == "INTERNAL"]
        require(rules, f"{p.name}: no INTERNAL forwarding rule (the address clients connect to)")
        fr = rules[0]
        require(p.linked(fr, "google_compute_region_backend_service", "backend_service"),
                f"{p.name}: the forwarding rule doesn't point at the backend service")
        require("8080" in [str(x) for x in (fr.get("ports") or [])], f"{p.name}: the forwarding rule must carry port 8080")


@requirement("R21.3", "Health checkers can reach the app VMs on 8080",
             hint='firewall rule: source_ranges ["130.211.0.0/22", "35.191.0.0/16"], target_tags ["app"], port 8080 - otherwise every VM is "unhealthy" and gets no traffic (and autohealing recreates them forever)')
def health_firewall(plan):
    fw = Firewall(plan)
    templates = [t for t in plan.resources("google_compute_instance_template") if t.module == "module.app"]
    require(templates, "No instance template in module.app")
    app = fw.instance(templates[0], "app VMs")
    for ip in HEALTH_CHECKERS:
        v = fw.evaluate(Firewall.internal_ip(ip, f"health checker {ip}"), app, "tcp", 8080)
        require(v, f"Health checker {ip} -> app:8080 is blocked: {v.reason}")


@requirement("R21.4", "Callers use the load balancer address, not a VM's",
             hint='output "app_internal_ip" = module.app_lb.ip_address')
def endpoint(plan):
    ilb_modules = {r.module for r in plan.resources("google_compute_forwarding_rule") if r.get("load_balancing_scheme") == "INTERNAL"}
    out = plan.outputs().get("app_internal_ip")
    require(out is not None, 'No output "app_internal_ip"')
    refs = plan.output_references("app_internal_ip")
    require(any(any(r.startswith(m + ".") or r == m for m in ilb_modules if m) or r.startswith("google_compute_forwarding_rule.") for r in refs),
            f"app_internal_ip refers to {refs or 'nothing'} - it should be the internal load balancer's address")


@requirement("R21.5", "prod has no single point of failure: every workload survives the loss of any zone",
             hint="Regional MIGs across 3 zones, Cloud SQL REGIONAL, a regional GKE cluster")
def no_spof(plan):
    prod = plan.others["prod"]
    worst = failure.worst_case(prod)
    spofs = [f"{a} (losing {worst[a][1]} leaves nothing)" for a in failure.single_points_of_failure(prod)]
    require(not spofs, "Single points of failure in prod:\n  " + "\n  ".join(spofs))


@requirement("R21.6", "prod keeps enough capacity after losing any zone (web 4, app 2 at minimum scale)",
             hint="With EVEN distribution over 3 zones, a zone holds ceil(n/3) VMs: web min 6 -> 4 left, app min 3 -> 2 left")
def capacity(plan):
    prod = plan.others["prod"]
    bad = []
    for tier, need in PROD_TARGETS.items():
        w = _workload(prod, tier)
        left, zone = failure.worst_case(prod)[w.address]
        if left < need:
            bad.append(f"{tier}: min {w.min_capacity} VMs over {len(w.zones)} zone(s) -> {left} left after losing {zone}, need {need}")
    require(not bad, "\n  ".join(bad))


@requirement("R21.7", "Regional MIGs spread VMs evenly, and say so",
             hint='distribution_policy_target_shape = "EVEN" in modules/mig-service; dev uses 2 zones, prod 3')
def even(plan):
    for p, zones in ((plan, 2), (plan.others["prod"], 3)):
        for m in p.resources("google_compute_region_instance_group_manager"):
            require(m.get("distribution_policy_target_shape") == "EVEN",
                    f"{p.name}: {m.address} target shape is {m.get('distribution_policy_target_shape') or 'unset'} - set EVEN explicitly")
            require(len(m.get("distribution_policy_zones") or []) >= zones, f"{p.name}: {m.address} must use at least {zones} zones")


@requirement("R21.8", "dev keeps the old app VM's data disk (forgotten, not deleted)",
             hint="removed { from = module.app.google_compute_disk.data  lifecycle { destroy = false } } in envs/dev")
def disk_kept(plan):
    d = plan.resource(DISK)
    require(d is not None, f"{DISK} isn't in the plan - was it removed from state by hand?")
    require(d.actions == ["forget"], f"{DISK} would be {'/'.join(d.actions)} - keep the data: Terraform should forget it")


@requirement("R21.9", "Deployed dev changes safely: only the old VM's own pieces are deleted",
             hint="Switching module \"app\" to mig-service keeps its service account and IAM; the VM, its disk attachment and snapshot schedule go away")
def safe(plan):
    bad = []
    for r in plan.all_changes():
        if r.is_replaced:
            bad.append(f"{r.address} would be REPLACED")
        elif r.actions == ["delete"] and r.address not in OLD_VM_PARTS:
            bad.append(f"{r.address} would be DESTROYED")
    require(not bad, "Against the deployed dev environment:\n  " + "\n  ".join(bad))
    kept = [a for a in ("module.app.google_service_account.this",) if plan.resource(a) is None or "create" in plan.resource(a).actions]
    require(not kept, f"The app tier's identity must be kept, not recreated: {kept}")


@requirement("R21.10", "prod and dev use the same modules",
             hint="Same module calls in both environments; only tfvars differ")
def prod(plan):
    srcs = lambda p: {n: c.get("source") for n, c in p.module_calls().items()}
    require(srcs(plan) == srcs(plan.others["prod"]), "dev and prod call different modules")


# ------------------------------------------------------------------ challenge
def _slo(plan):
    slos = plan.resources("google_monitoring_slo")
    require(slos, "No google_monitoring_slo")
    return slos[0]


@requirement("C21.1", "A 99.5% availability SLO over 28 days, measured at the load balancer",
             hint="google_monitoring_custom_service + google_monitoring_slo: goal 0.995, rolling_period_days 28, request_based_sli.good_total_ratio on loadbalancing.googleapis.com/https/request_count",
             level="challenge")
def slo(plan):
    s = _slo(plan)
    require(s.get("goal") == 0.995, f"goal is {s.get('goal')}: the target is 99.5%")
    require(s.get("rolling_period_days") == 28, "Use a rolling 28-day window")
    ratio = (s.get("request_based_sli.0.good_total_ratio") or [{}])
    ratio = ratio[0] if isinstance(ratio, list) and ratio else (ratio or {})
    text = " ".join(str(ratio.get(k) or "") for k in ("good_service_filter", "bad_service_filter", "total_service_filter"))
    require("loadbalancing.googleapis.com/https/request_count" in text, "The SLI must count load balancer requests")
    require(f"meridian-{plan.variable_value('environment')}-http" in text,
            "The SLI must be scoped to this environment's forwarding rule")


@requirement("C21.2", "Fast error-budget burn pages someone",
             hint='google_monitoring_alert_policy with filter select_slo_burn_rate("<slo id>", "3600s") > ~13.44 and a notification channel',
             level="challenge")
def burn(plan):
    blocks = [b for b in plan.source.blocks("resource", "google_monitoring_alert_policy") if "select_slo_burn_rate" in b.body]
    require(blocks, "No alert policy uses select_slo_burn_rate(...)")
    b = blocks[0]
    require("google_monitoring_slo." in b.body or "slo_id" in b.body, "The burn-rate filter must use the SLO's ID (google_monitoring_slo.<name>.id)")
    require("3600s" in b.body or "1h" in b.body, "Measure the burn rate over a short window (3600s) to catch fast burns")
    pols = [p for p in plan.resources("google_monitoring_alert_policy") if p.name == b.labels[1]]
    require(pols and (pols[0].get("notification_channels") or pols[0].is_unknown("notification_channels")), "The alert notifies nobody")


@requirement("C21.3", "prod's web tier survives a zone loss at peak (6 VMs left at maximum scale)",
             hint="max_replicas 9 over 3 zones -> 6 left", level="challenge")
def peak(plan):
    prod = plan.others["prod"]
    for tier, need in PROD_PEAK.items():
        w = _workload(prod, tier)
        left, zone = failure.worst_case(prod, at="max")[w.address]
        require(left >= need, f"{tier}: max {w.max_capacity} over {len(w.zones)} zones -> {left} left at peak after losing {zone}, need {need}")


@requirement("C21.4", "mig-service refuses single-zone groups and empty zones",
             hint="validation: length(var.zones) >= 2, and min_replicas >= length(var.zones); tests/challenge/modules/mig-service must pass",
             level="challenge")
def mig_validation(plan):
    src = plan.source
    zones = next(iter(src.blocks("variable", "zones", under="modules/mig-service")), None)
    mins = next(iter(src.blocks("variable", "min_replicas", under="modules/mig-service")), None)
    require(zones is not None and zones.block("validation"), "variable zones in modules/mig-service has no validation")
    require(mins is not None and mins.block("validation") and "var.zones" in mins.body,
            "min_replicas needs a validation that compares it with var.zones")
