"""Lesson 14 - Event-Driven Architecture.

`plan` is dev against the deployed lesson 13 environment.
"""

import re

from coursekit import iam
from coursekit.checks import require, requirement

APIS = {"pubsub.googleapis.com", "cloudscheduler.googleapis.com"}
AGENT_RE = re.compile(r"^serviceAccount:service-\d+@gcp-sa-pubsub\.iam\.gserviceaccount\.com$")


def _secs(v):
    m = re.match(r"(\d+(?:\.\d+)?)s$", str(v or ""))
    return float(m.group(1)) if m else 0.0


def _topics(plan):
    return plan.resources("google_pubsub_topic")


def _push_sub(plan):
    subs = [s for s in plan.resources("google_pubsub_subscription") if s.get("push_config")]
    require(len(subs) == 1, f"Expected one push subscription, found {len(subs)}")
    return subs[0]


def _dlq_topic(plan, sub):
    dl = (sub.get("dead_letter_policy") or [{}])[0]
    topics = plan.linked(sub, "google_pubsub_topic", "dead_letter_policy.dead_letter_topic")
    return dl, (topics[0] if topics else None)


def _worker(plan):
    svcs = [s for s in plan.resources("google_cloud_run_v2_service") if "worker" in str(s.get("name"))]
    require(len(svcs) == 1, "Expected one Cloud Run worker service (name containing 'worker')")
    return svcs[0]


def _sa(plan, account_id):
    s = [x for x in plan.resources("google_service_account") if x.get("account_id") == account_id]
    require(s, f"Service account {account_id} not found")
    return s[0]


# ------------------------------------------------------------------ lab
@requirement("R14.1", "Pub/Sub and Cloud Scheduler APIs are enabled",
             hint="Add pubsub.googleapis.com and cloudscheduler.googleapis.com to the foundation APIs.")
def apis(plan):
    missing = APIS - {r.get("service") for r in plan.resources("google_project_service")}
    require(not missing, "Missing APIs: " + ", ".join(sorted(missing)))


@requirement("R14.2", "Orders are pushed to the worker with an OIDC token from a dedicated identity",
             hint="google_pubsub_subscription on the orders topic: push_config { push_endpoint = <worker uri>  oidc_token { service_account_email = <push SA>  audience } }")
def push(plan):
    sub = _push_sub(plan)
    src = plan.linked(sub, "google_pubsub_topic", "topic")
    require(src, "The push subscription is not attached to a topic in this configuration")
    pc = (sub.get("push_config") or [{}])[0]
    worker = _worker(plan)
    require(plan.linked(sub, "google_cloud_run_v2_service", "push_config.push_endpoint"),
            "push_endpoint does not come from the worker service's uri")
    oidc = (pc.get("oidc_token") or [{}])[0]
    require(oidc, "No oidc_token: the worker would have to accept unauthenticated requests")
    sas = plan.linked(sub, "google_service_account", "push_config.oidc_token.service_account_email")
    require(sas, "The OIDC token should use a dedicated service account managed here")
    require(sas[0].get("account_id") not in ("meridian-app", "meridian-web", "meridian-ci"),
            f"Use a dedicated push identity, not {sas[0].get('account_id')}")
    require(oidc.get("audience") or sub.is_unknown("push_config.0.oidc_token.0.audience") or sub.references("push_config.oidc_token.audience"),
            "Set the OIDC audience (the worker URL) so tokens can't be replayed against other services")


@requirement("R14.3", "Delivery is retried with backoff and dead-lettered after a few attempts",
             hint="retry_policy { minimum_backoff = \"10s\"  maximum_backoff = \"600s\" } + dead_letter_policy { dead_letter_topic  max_delivery_attempts = 5 }; "
                  "expiration_policy { ttl = \"\" }")
def reliability(plan):
    sub = _push_sub(plan)
    rp = (sub.get("retry_policy") or [{}])[0]
    require(rp, "No retry_policy: failures are retried immediately, hammering a struggling worker")
    require(_secs(rp.get("minimum_backoff")) >= 10, f"minimum_backoff {rp.get('minimum_backoff')}: back off at least 10s")
    require(_secs(rp.get("maximum_backoff")) >= 60, f"maximum_backoff {rp.get('maximum_backoff')}: allow at least 60s")
    dl, dlq = _dlq_topic(plan, sub)
    require(dl and dlq is not None, "No dead_letter_policy pointing at a topic in this configuration - poison messages retry forever")
    src = plan.linked(sub, "google_pubsub_topic", "topic")
    require(not src or dlq.address != src[0].address, "The dead-letter topic must be a different topic")
    n = int(dl.get("max_delivery_attempts") or 0)
    require(5 <= n <= 10, f"max_delivery_attempts = {n}: 5-10 balances transient failures against poison messages")
    require(int(sub.get("ack_deadline_seconds") or 10) >= 30, "ack_deadline_seconds should cover the worker's processing time (>= 30)")
    ttl = ((sub.get("expiration_policy") or [{}])[0]).get("ttl")
    require(ttl == "", "Set expiration_policy { ttl = \"\" } - by default an idle subscription is deleted after 31 days")


@requirement("R14.4", "Dead letters are actually delivered and kept",
             hint="Pub/Sub service agent: publisher on the dead-letter topic + subscriber on the source subscription; a subscription on the dead-letter topic")
def dead_letters_work(plan):
    sub = _push_sub(plan)
    _, dlq = _dlq_topic(plan, sub)
    require(dlq is not None, "No dead-letter topic")
    grants = iam.grants(plan)
    agent = [g for g in grants if AGENT_RE.match(g.principal)]
    pub = [g for g in agent if g.scope == "topic" and g.role == "roles/pubsub.publisher" and g.target is not None and g.target.address == dlq.address]
    require(pub, "The Pub/Sub service agent can't publish to the dead-letter topic - failed messages would never be dead-lettered")
    ack = [g for g in agent if g.scope == "subscription" and g.role == "roles/pubsub.subscriber" and g.target is not None and g.target.address == sub.address]
    require(ack, "The Pub/Sub service agent needs roles/pubsub.subscriber on the source subscription to remove dead-lettered messages")
    keep = [s for s in plan.resources("google_pubsub_subscription")
            if any(t.address == dlq.address for t in plan.linked(s, "google_pubsub_topic", "topic"))]
    require(keep, "Nothing subscribes to the dead-letter topic - messages published there with no subscription are dropped")
    require(_secs(keep[0].get("message_retention_duration") or "604800s") >= 3 * 86400, "Keep dead letters at least 3 days")


@requirement("R14.5", "The worker is private and accepts only the push identity",
             hint='worker: ingress = "INGRESS_TRAFFIC_INTERNAL_ONLY", invoker IAM on, roles/run.invoker only for the push service account')
def worker_private(plan):
    w = _worker(plan)
    require(w.get("ingress") == "INGRESS_TRAFFIC_INTERNAL_ONLY", f"worker ingress is {w.get('ingress')}: it receives events, not users")
    require(w.get("invoker_iam_disabled") is not True, "invoker_iam_disabled must be false on the worker - every request needs a valid identity")
    grants = [g for g in iam.grants(plan) if g.scope == "run" and g.target is not None and g.target.address == w.address]
    require(not [g for g in grants if g.is_public], "The worker is publicly invokable")
    push_sas = plan.linked(_push_sub(plan), "google_service_account", "push_config.oidc_token.service_account_email")
    invokers = {g.principal for g in grants if g.role == "roles/run.invoker"}
    require(push_sas and invokers == {f"sa:{push_sas[0].address}"},
            f"roles/run.invoker on the worker should be exactly the push identity, found {sorted(invokers) or 'none'}")


@requirement("R14.6", "Only the API can publish, through a topic-level grant",
             hint="google_pubsub_topic_iam_member: roles/pubsub.publisher for meridian-app on the orders topic; no project-level Pub/Sub roles")
def publishers(plan):
    sub = _push_sub(plan)
    src = plan.linked(sub, "google_pubsub_topic", "topic")
    grants = iam.grants(plan)
    app = _sa(plan, "meridian-app")
    pubs = [g for g in grants if g.scope == "topic" and g.role == "roles/pubsub.publisher" and src and g.target is not None
            and g.target.address == src[0].address]
    require(any(g.principal == f"sa:{app.address}" for g in pubs), "meridian-app cannot publish order events")
    others = [g.principal for g in pubs if g.principal != f"sa:{app.address}"]
    require(not others, f"Others can publish to the orders topic: {others}")
    project = [f"{g.principal} {g.role}" for g in grants if g.scope == "project" and g.role.startswith("roles/pubsub.")]
    require(not project, f"Project-level Pub/Sub roles reach every topic: {project}")


@requirement("R14.7", "A nightly scheduled event, in an explicit time zone",
             hint='google_cloud_scheduler_job: schedule = "0 2 * * *", time_zone = "America/Chicago", pubsub_target { topic_name = <orders topic> }')
def scheduler(plan):
    jobs = plan.resources("google_cloud_scheduler_job")
    require(len(jobs) == 1, f"Expected one Cloud Scheduler job, found {len(jobs)}")
    j = jobs[0]
    tz = j.get("time_zone")
    require(tz and tz not in ("Etc/UTC", "UTC"),
            f"time_zone is {tz or 'unset'} (the provider default is UTC): Meridian's nightly jobs run in business time, America/Chicago")
    fields = str(j.get("schedule", "")).split()
    require(len(fields) == 5 and fields[2:] == ["*", "*", "*"], f"schedule '{j.get('schedule')}' should run once a day")
    require(plan.linked(j, "google_pubsub_topic", "pubsub_target.topic_name"), "The job does not publish to the events topic")


@requirement("R14.8", "The catalog keeps serving: its NEG is moved, not recreated",
             hint="Adding count to the NEG changes its address - add moved { from = ...this  to = ...this[0] } inside the module")
def catalog_kept(plan):
    negs = [r for r in plan.all_changes() if r.type == "google_compute_region_network_endpoint_group"]
    require(negs, "The catalog's serverless NEG is gone")
    for n in negs:
        require(n.actions in (["no-op"], ["update"]), f"{n.address} would be {n.actions} - the /api route would break during apply")
    catalog = [s for s in plan.resources("google_cloud_run_v2_service") if "catalog" in str(s.get("name"))]
    require(catalog and catalog[0].actions == ["no-op"], "The catalog service itself should not change")


@requirement("R14.9", "Deployed dev changes safely: additions only",
             hint="Nothing that exists should be replaced or destroyed.")
def safe(plan):
    bad = []
    for r in plan.all_changes():
        if r.is_replaced:
            bad.append(f"{r.address} would be REPLACED (forced by: " +
                       (", ".join(".".join(str(x) for x in p) for p in r.replace_paths) or "a force-new attribute") + ")")
        elif r.actions == ["delete"]:
            bad.append(f"{r.address} would be DESTROYED")
    require(not bad, "Against the deployed dev environment:\n  " + "\n  ".join(bad))


@requirement("R14.10", "prod runs the same pipeline with more worker capacity",
             hint="Same modules; prod order_worker_max_instances >= dev's")
def prod(plan):
    prod = plan.others["prod"]
    srcs = lambda p: {n: c.get("source") for n, c in p.configuration.get("root_module", {}).get("module_calls", {}).items()}
    require(srcs(plan) == srcs(prod), "dev and prod call different modules")
    mx = lambda p: int(((_worker(p).get("template.0") or {}).get("scaling") or [{}])[0].get("max_instance_count") or 0)
    require(mx(prod) >= mx(plan), f"prod worker max instances ({mx(prod)}) is below dev's ({mx(plan)})")
    require(prod.resources("google_cloud_scheduler_job"), "prod has no scheduler job")


# ------------------------------------------------------------------ challenge
@requirement("C14.1", "Events are validated against a schema at publish time",
             hint="google_pubsub_schema (AVRO or PROTOCOL_BUFFER) + schema_settings on the topic", level="challenge")
def schema(plan):
    require(plan.resources("google_pubsub_schema"), "No google_pubsub_schema")
    src = plan.linked(_push_sub(plan), "google_pubsub_topic", "topic")
    require(src and src[0].blocks("schema_settings"), "The orders topic has no schema_settings")


@requirement("C14.2", "The topic retains messages for replay",
             hint='message_retention_duration = "86400s" on the topic', level="challenge")
def topic_retention(plan):
    src = plan.linked(_push_sub(plan), "google_pubsub_topic", "topic")
    require(src and _secs(src[0].get("message_retention_duration")) >= 3600 * 12,
            "Keep at least 12h of messages on the topic so a new or reset subscription can replay")


@requirement("C14.3", "The worker only receives the event types it handles",
             hint='filter = "attributes.event_type = \\"order.created\\" OR ..." on the push subscription', level="challenge")
def filtered(plan):
    f = _push_sub(plan).get("filter") or ""
    require("attributes.event_type" in f, "The push subscription has no attribute filter")


@requirement("C14.4", "The pipeline module rejects invalid delivery-attempt limits",
             hint="validation 5-100 on max_delivery_attempts; tests/challenge/event_pipeline.tftest.hcl must pass", level="challenge",
             test="event_pipeline.tftest.hcl")
def attempts_validation(plan):
    mods = plan.configuration.get("root_module", {}).get("module_calls", {})
    require(any("max_delivery_attempts" in m.get("module", {}).get("variables", {}) for m in mods.values()),
            "No module declares max_delivery_attempts")
