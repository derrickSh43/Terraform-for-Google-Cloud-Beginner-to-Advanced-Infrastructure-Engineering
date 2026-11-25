"""Lesson 13 - Serverless Infrastructure.

`plan` is dev against the deployed lesson 12 environment.
"""

import ipaddress
import itertools
import re

from coursekit import iam, lb
from coursekit.checks import require, requirement

APIS = {"run.googleapis.com", "artifactregistry.googleapis.com"}
DIGEST_RE = re.compile(r"^(?P<region>[a-z0-9-]+)-docker\.pkg\.dev/(?P<project>[^/]+)/(?P<repo>[^/]+)/[^@]+@sha256:[0-9a-f]{64}$")


def _run(plan):
    s = plan.resources("google_cloud_run_v2_service")
    require(len(s) == 1, f"Expected one google_cloud_run_v2_service, found {len(s)}")
    return s[0]


def _tmpl(svc):
    return svc.get("template.0") or {}


def _container(svc):
    cs = _tmpl(svc).get("containers") or []
    require(len(cs) == 1, f"Expected one container, found {len(cs)}")
    return cs[0]


def _repo(plan):
    r = plan.resources("google_artifact_registry_repository")
    require(len(r) == 1, f"Expected one Artifact Registry repository, found {len(r)}")
    return r[0]


def _run_sa(plan, svc):
    email = _tmpl(svc).get("service_account")
    sas = [s for s in plan.resources("google_service_account") if s.get("email") == email]
    if not sas:
        sas = plan.linked(svc, "google_service_account", "template.service_account")
    return email, (sas[0] if sas else None)


def _mem_gib(v):
    m = re.match(r"(\d+(?:\.\d+)?)(Mi|Gi|M|G)?$", str(v))
    if not m:
        return 99
    n = float(m.group(1))
    return n / 1024 if m.group(2) in ("Mi", "M") else n


# ------------------------------------------------------------------ lab
@requirement("R13.1", "Cloud Run and Artifact Registry APIs are enabled",
             hint="Add run.googleapis.com and artifactregistry.googleapis.com to the foundation APIs.")
def apis(plan):
    missing = APIS - {r.get("service") for r in plan.resources("google_project_service")}
    require(not missing, "Missing APIs: " + ", ".join(sorted(missing)))


@requirement("R13.2", "A regional Docker repository with cleanup policies; only CI can push",
             hint='google_artifact_registry_repository (format DOCKER, location = region, cleanup_policies DELETE untagged + KEEP recent) '
                  '+ repository-level roles/artifactregistry.writer for meridian-ci')
def registry(plan):
    r = _repo(plan)
    require(r.get("format") == "DOCKER", f"format is {r.get('format')}")
    region = plan.variable_value("region")
    require(r.get("location") == region, f"Repository location {r.get('location')}: keep images in {region}, next to Cloud Run")
    actions = {p.get("action") for p in r.blocks("cleanup_policies")}
    require({"DELETE", "KEEP"} <= actions, f"Cleanup policies {sorted(actions) or 'none'}: delete old untagged images but KEEP recent ones for rollback")
    require(r.get("cleanup_policy_dry_run") is not True, "cleanup_policy_dry_run is true - policies would never delete anything")
    grants = iam.grants(plan)
    ci = [s for s in plan.resources("google_service_account") if s.get("account_id") == "meridian-ci"]
    require(ci, "meridian-ci not found")
    repo_writers = [g for g in grants if g.scope == "repository" and g.role == "roles/artifactregistry.writer"]
    require(any(g.principal == f"sa:{ci[0].address}" for g in repo_writers), "meridian-ci cannot push to the repository")
    require(all(g.principal == f"sa:{ci[0].address}" for g in repo_writers), "Only CI should be able to push images")
    proj = [f"{g.principal} {g.role}" for g in grants if g.scope == "project" and g.role.startswith("roles/artifactregistry.")]
    require(not proj, f"Project-level Artifact Registry roles: {proj}")


@requirement("R13.3", "The service runs as its own service account, with no project roles",
             hint="google_service_account meridian-catalog; template.service_account = its email (never the default compute SA)")
def identity(plan):
    svc = _run(plan)
    email, sa = _run_sa(plan, svc)
    require(email or sa, "template.service_account is not set - Cloud Run would use the default compute service account (Editor!)")
    require(not str(email or "").endswith("-compute@developer.gserviceaccount.com"), "Don't run as the default compute service account")
    require(sa is not None, "The service account is not managed in this configuration")
    roles = [g.role for g in iam.for_principal(iam.grants(plan), f"sa:{sa.address}", "project")]
    require(not roles, f"{sa.get('account_id')} has project roles {roles} - it only needs to read one secret")


@requirement("R13.4", "The image is pinned by digest from this project's registry",
             hint='"us-central1-docker.pkg.dev/<project>/meridian/catalog@sha256:<64 hex>" - not :latest or any tag')
def image(plan):
    img = _container(_run(plan)).get("image", "")
    m = DIGEST_RE.match(img)
    require(m, f"Image '{img}' is not an Artifact Registry image pinned by digest - tags can be moved to different bytes")
    require(m.group("project") == plan.variable_value("project_id"), f"Image comes from project {m.group('project')}, not this project")
    require(m.group("region") == plan.variable_value("region"), f"Image is in {m.group('region')}: pull from the service's region")


@requirement("R13.5", "Only the load balancer can reach the service; nothing is public",
             hint='ingress = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER", no allUsers / allAuthenticatedUsers invoker bindings')
def ingress(plan):
    svc = _run(plan)
    ing = svc.get("ingress", "INGRESS_TRAFFIC_ALL")
    public = [f"{g.principal} {g.role}" for g in iam.grants(plan) if g.scope == "run" and g.is_public]
    require(not public, f"The service is invokable by the whole internet: {public}")
    require(ing in ("INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER", "INGRESS_TRAFFIC_INTERNAL_ONLY"),
            f"ingress = {ing}: the *.run.app URL would be reachable from anywhere, bypassing the load balancer")


@requirement("R13.6", "Scaling and resources are bounded",
             hint="scaling { min_instance_count = 0 (dev)  max_instance_count <= 10 }, cpu <= 2, memory <= 2Gi, max_instance_request_concurrency set")
def bounds(plan):
    svc = _run(plan)
    sc = (_tmpl(svc).get("scaling") or [{}])[0]
    mx = int(sc.get("max_instance_count") or 100)
    require(mx <= 10, f"max_instance_count = {mx}: unbounded scaling can exhaust Cloud SQL connections and the budget")
    require(int(sc.get("min_instance_count") or 0) == 0, "dev should scale to zero (min_instance_count = 0)")
    lim = ((_container(svc).get("resources") or [{}])[0].get("limits") or {})
    require(lim, "Set resources.limits (cpu, memory)")
    require(float(str(lim.get("cpu", "99")).rstrip("m") or 99) <= 2, f"cpu limit {lim.get('cpu')}: <= 2")
    require(_mem_gib(lim.get("memory", "99Gi")) <= 2, f"memory limit {lim.get('memory')}: <= 2Gi")
    require(_tmpl(svc).get("max_instance_request_concurrency"), "Set max_instance_request_concurrency")


@requirement("R13.7", "The service reaches the database privately, with the password from Secret Manager",
             hint='vpc_access { egress = "PRIVATE_RANGES_ONLY"  network_interfaces { subnetwork = <serverless subnet> } }; '
                  "DB_PASSWORD via value_source.secret_key_ref; secretAccessor on the DB secret")
def db_wiring(plan):
    svc = _run(plan)
    va = (_tmpl(svc).get("vpc_access") or [{}])[0]
    require(va, "No vpc_access: the service can't reach Cloud SQL's private IP")
    require(va.get("egress") == "PRIVATE_RANGES_ONLY", f"egress = {va.get('egress')}: route only private ranges through the VPC")
    require(plan.linked(svc, "google_compute_subnetwork", "template.vpc_access.network_interfaces.subnetwork")
            or ((va.get("network_interfaces") or [{}])[0].get("subnetwork")), "Direct VPC egress needs a subnetwork")
    envs = _container(svc).get("env") or []
    plain = [e.get("name") for e in envs if re.search(r"PASS|SECRET|TOKEN", e.get("name", ""), re.I) and e.get("value")]
    require(not plain, f"Secrets passed as plain env values: {plain} - they show up in the console and revision history")
    secret_envs = [e for e in envs if ((e.get("value_source") or [{}])[0].get("secret_key_ref"))]
    require(secret_envs, "No environment variable reads from Secret Manager (value_source.secret_key_ref)")
    email, sa = _run_sa(plan, svc)
    secret = plan.resources("google_secret_manager_secret")
    ok = sa is not None and any(g.scope == "secret" and g.principal == f"sa:{sa.address}" and g.role == "roles/secretmanager.secretAccessor"
                                for g in iam.grants(plan))
    require(ok, "The Cloud Run service account cannot read the DB password secret")


@requirement("R13.8", "The load balancer sends /api/* to Cloud Run and everything else to the web MIG",
             hint="url_map path_matcher with path_rule /api/* -> backend service whose backend is the serverless NEG (cloud_run { service })")
def routing(plan):
    maps = plan.resources("google_compute_url_map")
    pms = [(m, pm) for m in maps for pm in m.blocks("path_matcher")]
    require(pms, "No path_matcher on the URL map")
    api_backend = None
    for m, pm in pms:
        for rule in pm.get("path_rule") or []:
            if any(p in ("/api/*", "/api/**") for p in rule.get("paths") or []):
                cands = plan.linked(m, "google_compute_backend_service", "path_matcher.path_rule.service")
                api_backend = next((c for c in cands if c.address.endswith(".api") or "api" in c.address), cands[0] if cands else None)
    require(api_backend is not None, 'No path_rule sends "/api/*" to a backend service')
    negs = plan.linked(api_backend, "google_compute_region_network_endpoint_group", "backend.group")
    require(negs, f"{api_backend.address} is not backed by a network endpoint group")
    neg = negs[0]
    require(neg.get("network_endpoint_type") == "SERVERLESS", "The NEG must be SERVERLESS")
    require(plan.linked(neg, "google_cloud_run_v2_service", "cloud_run.service") or (neg.get("cloud_run.0") or {}).get("service"),
            "The serverless NEG does not point at the Cloud Run service")
    web = [g for f in lb.trace(plan) for b in f.backends for g in b.groups]
    require(any("instance_group_manager" in g.type for g in web), "The default route no longer reaches the web MIG")


@requirement("R13.9", "Deployed dev changes safely: additions only",
             hint="The URL map changes in place; nothing is destroyed or replaced.")
def safe(plan):
    bad = []
    for r in plan.all_changes():
        if r.is_replaced:
            bad.append(f"{r.address} would be REPLACED (forced by: " +
                       (", ".join(".".join(str(x) for x in p) for p in r.replace_paths) or "a force-new attribute") + ")")
        elif r.actions == ["delete"]:
            bad.append(f"{r.address} would be DESTROYED")
    require(not bad, "Against the deployed dev environment:\n  " + "\n  ".join(bad))


@requirement("R13.10", "prod keeps an instance warm; every subnet range stays unique",
             hint="prod catalog_min_instances = 1; serverless subnets 10.10.3.0/24 (dev) and 10.20.3.0/24 (prod)")
def prod(plan):
    prod = plan.others["prod"]
    srcs = lambda p: {n: c.get("source") for n, c in p.configuration.get("root_module", {}).get("module_calls", {}).items()}
    require(srcs(plan) == srcs(prod), "dev and prod call different modules")
    sc = (_tmpl(_run(prod)).get("scaling") or [{}])[0]
    require(int(sc.get("min_instance_count") or 0) >= 1, "prod should keep >= 1 instance warm (no cold starts for shoppers)")
    nets = [(env, s.get("name"), ipaddress.ip_network(s.get("ip_cidr_range"), strict=False))
            for env, p in (("dev", plan), ("prod", prod)) for s in p.resources("google_compute_subnetwork") if s.get("ip_cidr_range")]
    for (e1, n1, a), (e2, n2, b) in itertools.combinations(nets, 2):
        require(not a.overlaps(b), f"{e1} {n1} ({a}) overlaps {e2} {n2} ({b})")


# ------------------------------------------------------------------ challenge
@requirement("C13.1", "prod runs a canary: most traffic on a pinned revision, a small share on latest",
             hint="traffic blocks: REVISION (stable, 90%) + LATEST (10%)", level="challenge")
def canary(plan):
    svc = _run(plan.others["prod"])
    traffic = svc.get("traffic") or []
    require(len(traffic) >= 2, "prod has a single traffic target - no canary")
    require(sum(int(t.get("percent") or 0) for t in traffic) == 100, "Traffic percentages must add up to 100")
    pinned = [t for t in traffic if t.get("type") == "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION" and t.get("revision")]
    latest = [t for t in traffic if t.get("type") == "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"]
    require(pinned and latest, "Need one pinned REVISION target and one LATEST target")
    require(int(latest[0].get("percent") or 0) <= 50, "The canary (latest) should get the smaller share")


@requirement("C13.2", "Startup and liveness probes on /healthz",
             hint="startup_probe { http_get { path = \"/healthz\" } } and liveness_probe", level="challenge")
def probes(plan):
    c = _container(_run(plan))
    for name in ("startup_probe", "liveness_probe"):
        p = (c.get(name) or [{}])[0]
        require(p and (p.get("http_get") or p.get("tcp_socket") or p.get("grpc")), f"No {name}")


@requirement("C13.3", "Release images are never cleaned up",
             hint='cleanup_policies KEEP with condition { tag_state = "TAGGED"  tag_prefixes = ["release-"] }', level="challenge")
def keep_releases(plan):
    keeps = [p for p in _repo(plan).blocks("cleanup_policies") if p.get("action") == "KEEP"]
    require(any("release-" in str(((p.get("condition") or [{}])[0]).get("tag_prefixes") or []) for p in keeps),
            "No KEEP policy protects release-* tags")


@requirement("C13.4", "The Cloud Run module refuses tags and foreign registries",
             hint="validation on var.image; tests/challenge/cloud_run_module.tftest.hcl must pass", level="challenge",
             test="cloud_run_module.tftest.hcl")
def image_validation(plan):
    mods = plan.configuration.get("root_module", {}).get("module_calls", {})
    require(any("image" in m.get("module", {}).get("variables", {}) for m in mods.values()), "No module declares var.image")
