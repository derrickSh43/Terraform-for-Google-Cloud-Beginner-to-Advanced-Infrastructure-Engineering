"""Lesson 17 - Logging, Monitoring, and Observability.

`plan` is dev against the deployed lesson 16 environment.
"""

import re

from coursekit.checks import require, requirement

DAY = 86400


def _policies(plan):
    p = plan.resources("google_monitoring_alert_policy")
    require(p, "No google_monitoring_alert_policy resources")
    return p


def _conds(policy):
    return [(c, (c.get("condition_threshold") or [{}])[0]) for c in policy.get("conditions") or []]


def _filter_has(plan, policy, *needles):
    """True when a condition filter (value or, if unknown, the HCL expression) contains all needles."""
    for c, th in _conds(policy):
        text = th.get("filter") or ""
        if not text:
            name = policy.address.split(".")[-1].split("[")[0]
            for blk in plan.source.blocks("resource", "google_monitoring_alert_policy", name):
                for cond in blk.blocks("conditions"):
                    for ct in cond.blocks("condition_threshold"):
                        text += ct.attr("filter") or ""
        if all(n in text for n in needles):
            return True
    return False


def _policy_for(plan, *needles):
    found = [p for p in _policies(plan) if _filter_has(plan, p, *needles)]
    return found[0] if found else None


def _secs(v):
    m = re.match(r"(\d+)s$", str(v or ""))
    return int(m.group(1)) if m else 0


def _lb_ip(plan):
    addrs = [a for a in plan.resources("google_compute_global_address") if not a.get("purpose")]
    return addrs[0].get("address") if addrs else None


# ------------------------------------------------------------------ lab
@requirement("R17.1", "Every alert reaches a human",
             hint="google_monitoring_notification_channel (email) and notification_channels = [<channel>.id] on every alert policy")
def channels(plan):
    chans = plan.resources("google_monitoring_notification_channel")
    require(chans, "No notification channel - alerts would fire into the void")
    silent = [p.get("display_name") or p.address for p in _policies(plan)
              if not (p.get("notification_channels") or p.references_type("google_monitoring_notification_channel", "notification_channels"))]
    require(not silent, f"Alert policies with no notification channel: {silent}")


@requirement("R17.2", "An uptime check probes the storefront through the load balancer",
             hint='google_monitoring_uptime_check_config: monitored_resource uptime_url with host = the LB IP, http_check path "/", period 60s, timeout 10s')
def uptime(plan):
    checks = plan.resources("google_monitoring_uptime_check_config")
    require(len(checks) == 1, f"Expected one uptime check, found {len(checks)}")
    u = checks[0]
    mr = u.get("monitored_resource.0") or {}
    require(mr.get("type") == "uptime_url", f"monitored_resource type {mr.get('type')}: use uptime_url for a public endpoint")
    host = (mr.get("labels") or {}).get("host")
    ip = _lb_ip(plan)
    require(host and (ip is None or host == ip) or u.references_type("google_compute_global_address", "monitored_resource"),
            f"The uptime check probes {host!r}, not the load balancer IP {ip!r}")
    require((u.get("http_check.0") or {}).get("path"), "Set http_check.path")
    period, timeout = _secs(u.get("period")), _secs(u.get("timeout"))
    require(0 < period <= 300, f"period {u.get('period')}: probe at least every 5 minutes")
    require(0 < timeout < period, f"timeout {u.get('timeout')} must be shorter than the period")


@requirement("R17.3", "An alert fires when the uptime check fails",
             hint='condition filter on monitoring.googleapis.com/uptime_check/check_passed for this check, duration >= 60s')
def uptime_alert(plan):
    p = _policy_for(plan, "uptime_check/check_passed")
    require(p, "No alert policy watches uptime_check/check_passed")
    require(p.references_type("google_monitoring_uptime_check_config", "conditions") or _filter_has(plan, p, "check_id"),
            "The uptime alert should filter on this check's check_id")
    th = _conds(p)[0][1]
    require(_secs(th.get("duration")) >= 60, "duration < 60s would page on a single failed probe")


@requirement("R17.4", "An alert fires when more than 5% of requests fail",
             hint="ratio condition: filter = 5xx request_count, denominator_filter = all request_count, threshold_value <= 0.05")
def errors(plan):
    p = _policy_for(plan, "loadbalancing.googleapis.com/https/request_count", "500")
    require(p, "No alert on load balancer 5xx responses")
    th = [th for _, th in _conds(p) if th.get("denominator_filter")]
    require(th, "Alert on the 5xx *ratio* (denominator_filter = all requests), not a raw count that grows with traffic")
    require(0 < float(th[0].get("threshold_value") or 0) <= 0.05, f"threshold_value {th[0].get('threshold_value')}: alert at <= 5% errors")
    require(_secs(th[0].get("duration")) >= 60, "Use a duration of at least 60s to avoid paging on single spikes")


@requirement("R17.5", "An alert fires when order events are dead-lettered",
             hint="num_undelivered_messages on the dead-letter subscription > 0 (lesson 14)")
def dead_letters(plan):
    p = _policy_for(plan, "num_undelivered_messages")
    require(p, "No alert on undelivered Pub/Sub messages")
    require(_filter_has(plan, p, "dead-letter") or _filter_has(plan, p, "dead_letter"),
            "The backlog alert should watch the dead-letter subscription - that's where stuck orders end up")


@requirement("R17.6", "Every alert has a runbook and a severity",
             hint='documentation { mime_type = "text/markdown"  content = "<what happened, first steps, runbook link>" }, severity, enabled = true')
def runbooks(plan):
    for p in _policies(plan):
        doc = (p.get("documentation") or [{}])[0]
        name = p.get("display_name") or p.address
        require(len((doc.get("content") or "").strip()) >= 40, f"'{name}' has no useful documentation - on-call needs first steps at 3 a.m.")
        require(p.get("severity") in ("CRITICAL", "ERROR", "WARNING"), f"'{name}' has no severity")
        require(p.get("enabled") is not False, f"'{name}' is disabled")


@requirement("R17.7", "Worker errors are a metric",
             hint='google_logging_metric with filter on resource.type="cloud_run_revision", the worker service name and severity>=ERROR')
def log_metric(plan):
    metrics = plan.resources("google_logging_metric")
    require(metrics, "No log-based metric")
    f = metrics[0].get("filter") or ""
    require("severity>=ERROR" in f.replace(" ", ""), "The log metric should count ERROR (and worse) entries")
    require("cloud_run_revision" in f and "order-worker" in f, "Filter on the order worker's Cloud Run logs")


@requirement("R17.8", "Secret reads are audited",
             hint='google_project_iam_audit_config { service = "secretmanager.googleapis.com"  audit_log_config { log_type = "DATA_READ" } }')
def audit_config(plan):
    cfgs = [c for c in plan.resources("google_project_iam_audit_config") if c.get("service") in ("secretmanager.googleapis.com", "allServices")]
    require(cfgs, "Data Access audit logs are not enabled for Secret Manager - nobody would know who read the DB password")
    types = {t.get("log_type") for c in cfgs for t in c.get("audit_log_config") or []}
    require("DATA_READ" in types, f"Audit log types {sorted(types)}: DATA_READ records secret access")


@requirement("R17.9", "Audit logs are sunk to a retention-protected bucket",
             hint='google_logging_project_sink (filter logName:"cloudaudit.googleapis.com", unique_writer_identity) -> bucket with retention >= 90 days; '
                  "objectCreator on that bucket for the sink's writer_identity")
def audit_sink(plan):
    sinks = plan.resources("google_logging_project_sink")
    require(sinks, "No log sink")
    s = sinks[0]
    require("cloudaudit.googleapis.com" in (s.get("filter") or ""), "The sink should export audit logs (logName:\"cloudaudit.googleapis.com\")")
    require(s.get("unique_writer_identity") is True, "Use unique_writer_identity so the sink has its own identity")
    dest = s.get("destination") or ""
    buckets = [b for b in plan.resources("google_storage_bucket") if b.get("name") and b.get("name") in dest] or \
              plan.linked(s, "google_storage_bucket", "destination")
    require(buckets, f"The sink's destination {dest!r} is not a bucket in this configuration")
    b = buckets[0]
    secs = int((b.get("retention_policy.0") or {}).get("retention_period") or 0)
    require(secs >= 90 * DAY, f"Audit bucket retention is {secs // DAY} days: keep audit logs >= 90 days, undeletable")
    require(b.get("public_access_prevention") == "enforced" and b.get("uniform_bucket_level_access") is True,
            "The audit bucket needs uniform access and public access prevention")
    grants = [g for g in plan.resources("google_storage_bucket_iam_member")
              if g.references_type("google_logging_project_sink", "member")]
    require(grants, "The sink's writer_identity has no permission on the bucket - nothing would be written")
    require(all(g.get("role") == "roles/storage.objectCreator" for g in grants), "The sink only needs roles/storage.objectCreator")


@requirement("R17.10", "Deployed dev changes safely; prod keeps audit logs longer",
             hint="Additions only. prod audit_retention_days >= 365.")
def safe(plan):
    bad = [f"{r.address} would be {'REPLACED' if r.is_replaced else 'DESTROYED'}" for r in plan.all_changes()
           if r.is_replaced or r.actions == ["delete"]]
    require(not bad, "Against the deployed dev environment:\n  " + "\n  ".join(bad))
    prod = plan.others["prod"]
    srcs = lambda p: {n: c.get("source") for n, c in p.configuration.get("root_module", {}).get("module_calls", {}).items()}
    require(srcs(plan) == srcs(prod), "dev and prod call different modules")
    keep = lambda p: max([int((b.get("retention_policy.0") or {}).get("retention_period") or 0) // DAY
                          for b in p.resources("google_storage_bucket") if "audit" in str(b.get("name"))] or [0])
    require(keep(prod) >= 365, f"prod keeps audit logs {keep(prod)} days - at least a year")


# ------------------------------------------------------------------ challenge
@requirement("C17.1", "An availability SLO with a fast-burn alert",
             hint="google_monitoring_custom_service + google_monitoring_slo (request_based_sli, goal 0.995, 28 days) + alert on select_slo_burn_rate(...) > 10",
             level="challenge")
def slo(plan):
    slos = plan.resources("google_monitoring_slo")
    require(slos, "No SLO")
    s = slos[0]
    require(0.9 <= float(s.get("goal") or 0) < 1, f"goal {s.get('goal')}: a realistic availability target is 0.99-0.999")
    require(s.get("rolling_period_days") or s.get("calendar_period"), "Set the SLO window")
    require(any(_filter_has(plan, p, "select_slo_burn_rate") for p in _policies(plan)), "No burn-rate alert on the SLO")


@requirement("C17.2", "A dashboard for the storefront",
             hint="google_monitoring_dashboard with widgets for request classes and Cloud SQL CPU", level="challenge")
def dashboard(plan):
    d = plan.resources("google_monitoring_dashboard")
    require(d and "loadbalancing.googleapis.com" in (d[0].get("dashboard_json") or ""), "No dashboard showing load balancer traffic")


@requirement("C17.3", "An alert on sustained Cloud SQL CPU",
             hint="cloudsql.googleapis.com/database/cpu/utilization > 0.8 for >= 5 minutes", level="challenge")
def sql_cpu(plan):
    p = _policy_for(plan, "cloudsql.googleapis.com/database/cpu/utilization")
    require(p, "No Cloud SQL CPU alert")
    th = _conds(p)[0][1]
    require(0.5 <= float(th.get("threshold_value") or 0) <= 0.95, "Use a CPU threshold between 50% and 95%")
    require(_secs(th.get("duration")) >= 300, "Require at least 5 minutes of high CPU")


@requirement("C17.4", "The module rejects a malformed on-call address",
             hint="validation on oncall_email; tests/challenge/observability_module.tftest.hcl must pass", level="challenge")
def email_validation(plan):
    mods = plan.configuration.get("root_module", {}).get("module_calls", {})
    require(any("oncall_email" in m.get("module", {}).get("variables", {}) for m in mods.values()), "No module declares oncall_email")
