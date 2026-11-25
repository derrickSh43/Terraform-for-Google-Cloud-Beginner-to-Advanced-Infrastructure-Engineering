"""Lesson 23 - Enterprise Architecture and Platform Engineering.

`plan` is dev against the deployed lesson 22 environment (it must not change);
`plan.others["platform"]` is the new landing-zone root (organisation-level, planned with fake IDs).
"""

import re

from coursekit.checks import require, requirement

REQUIRED_LABELS = ("app", "env", "cost-center", "owner", "managed_by")
GUARDRAILS = {"compute.skipDefaultNetworkCreation", "iam.disableServiceAccountKeyCreation"}


def _platform(plan):
    return plan.others["platform"]


def _top(p):
    tops = [f for f in p.resources("google_folder") if str(f.get("parent") or "").startswith("organizations/")]
    require(len(tops) == 1, f"Expected one top folder directly under the organization, found {len(tops)}")
    return tops[0]


def _children(p, top):
    return [f for f in p.resources("google_folder") if f is not top and top in p.linked(f, "google_folder", "parent")]


def _projects(p):
    projs = p.resources("google_project")
    require(projs, "The platform creates no projects")
    return projs


def _key(r):
    return r.index if isinstance(r.index, str) else r.address


def _on_top(p, r, path):
    top = _top(p)
    return top in p.linked(r, "google_folder", path)


# ------------------------------------------------------------------ lab
@requirement("R23.1", "A Meridian folder under the organization, with dev, prod and shared folders under it",
             hint='google_folder "meridian" (parent = "organizations/${var.org_id}") and google_folder "env" for_each dev/prod/shared (parent = the Meridian folder)')
def hierarchy(plan):
    p = _platform(plan)
    top = _top(p)
    names = sorted(str(f.get("display_name")) for f in _children(p, top))
    require({"dev", "prod", "shared"} <= set(names), f"Folders under {top.get('display_name')}: {names} - need dev, prod and shared")
    unprotected = [f.address for f in p.resources("google_folder") if f.get("deletion_protection") is False]
    require(not unprotected, f"Folders without deletion protection: {unprotected}")


@requirement("R23.2", "Projects come from one factory module and land in their environment's folder",
             hint="modules/project-factory with for_each over var.projects; folder_id = var.folders[each.value.folder]; dev projects in dev, shared in shared")
def factory(plan):
    p = _platform(plan)
    projs = _projects(p)
    mods = {r.module for r in projs}
    require(len(mods) == 1 and "" not in mods, f"Projects are created in {sorted(m or 'the root' for m in mods)} - use one factory module")
    call = p.module_calls().get(next(iter(mods)).split(".")[1], {})
    require(str(call.get("source", "")).rstrip("/").endswith("project-factory"), "Projects must come from modules/project-factory")
    folders = [f for f in p.resources("google_folder")]
    unplaced = [r.address for r in projs if not any(f in folders for f in p.linked(r, "google_folder", "folder_id"))]
    require(not unplaced, f"Projects not placed in a landing-zone folder: {unplaced}")
    spec = p.variable_value("projects") or {}
    wrong = [f"{k}: env {v.get('env')} in folder {v.get('folder')}" for k, v in spec.items()
             if v.get("folder") != v.get("env")]
    require(not wrong, "Projects in the wrong environment folder:\n  " + "\n  ".join(wrong))


@requirement("R23.3", "Every project carries the mandatory labels and safe defaults",
             hint='labels app, env, cost-center (cc-NNNN), owner, managed_by; auto_create_network = false; deletion_policy = "PREVENT"')
def labels(plan):
    p = _platform(plan)
    bad = []
    for r in _projects(p):
        lab = r.get("labels") or {}
        missing = [k for k in REQUIRED_LABELS if not lab.get(k)]
        if missing:
            bad.append(f"{r.address}: missing labels {missing}")
        elif not re.fullmatch(r"cc-\d{4}", str(lab.get("cost-center"))):
            bad.append(f"{r.address}: cost-center {lab.get('cost-center')!r} isn't cc-NNNN")
        if r.get("auto_create_network") is not False:
            bad.append(f"{r.address}: auto_create_network must be false")
        if r.get("deletion_policy") != "PREVENT":
            bad.append(f"{r.address}: deletion_policy is {r.get('deletion_policy')}, use PREVENT")
    require(not bad, "\n  ".join(bad))
    var = next(iter(p.source.blocks("variable", "projects", under="modules/project-factory")), None)
    require(var is not None and len(var.blocks("validation")) >= 2,
            "The factory must validate its input (env, cost_center format, owner) - labels are enforced, not hoped for")


@requirement("R23.4", "Every project has a budget with an early warning and a 100% alert",
             hint="google_billing_budget for_each = var.projects, budget_filter.projects = [projects/<number>], thresholds 0.5, 0.9, 1.0 (+ forecast)")
def budgets(plan):
    p = _platform(plan)
    projs = {_key(r): r for r in _projects(p)}
    buds = {_key(b): b for b in p.resources("google_billing_budget")}
    missing = sorted(set(projs) - set(buds))
    require(not missing, f"Projects without a budget: {missing}")
    for k, b in buds.items():
        require(b.references_type("google_project", "budget_filter"), f"Budget {k} isn't scoped to a project (budget_filter.projects)")
        th = [float(t.get("threshold_percent") or 0) for t in b.blocks("threshold_rules")]
        require(any(t >= 1.0 for t in th), f"Budget {k} has no 100% threshold")
        require(any(t < 1.0 for t in th), f"Budget {k} has no early warning below 100%")
        units = ((b.get("amount") or [{}])[0].get("specified_amount") or [{}])[0].get("units")
        require(units and float(units) > 0, f"Budget {k} has no amount")


@requirement("R23.5", "One Shared VPC host; the workload projects are its service projects",
             hint="google_compute_shared_vpc_host_project for meridian-network; google_compute_shared_vpc_service_project for each project with shared_vpc = true")
def shared_vpc(plan):
    p = _platform(plan)
    hosts = p.resources("google_compute_shared_vpc_host_project")
    require(len(hosts) == 1, f"Expected one Shared VPC host project, found {len(hosts)}")
    svc = {_key(s) for s in p.resources("google_compute_shared_vpc_service_project")}
    spec = p.variable_value("projects") or {}
    want = {k for k, v in spec.items() if v.get("env") in ("dev", "prod")}
    require(want and want <= svc, f"Workload projects not attached to the Shared VPC: {sorted(want - svc)}")
    extra = svc - want
    require(not extra, f"Shared projects must not be service projects (they'd see workload subnets): {sorted(extra)}")


@requirement("R23.6", "All logs under the Meridian folder flow to one central log bucket, kept 400 days",
             hint='google_logging_folder_sink on the Meridian folder, include_children = true, destination = "logging.googleapis.com/<bucket id>"; google_logging_project_bucket_config retention_days >= 365')
def central_logs(plan):
    p = _platform(plan)
    sinks = p.resources("google_logging_folder_sink")
    require(sinks, "No folder-level log sink")
    s = sinks[0]
    require(_on_top(p, s, "folder"), "The sink must be on the Meridian folder (so every project below is included)")
    require(s.get("include_children") is True, "include_children = true - otherwise only the folder's own logs are exported")
    require(s.references_type("google_logging_project_bucket_config", "destination"), "The destination must be the central log bucket")
    buckets = p.resources("google_logging_project_bucket_config")
    require(buckets and int(buckets[0].get("retention_days") or 0) >= 365,
            f"Central logs retention is {buckets[0].get('retention_days') if buckets else 'unset'} days; keep at least 365")


@requirement("R23.7", "The sink's identity may write to the log bucket",
             hint="google_project_iam_member roles/logging.bucketWriter, member = google_logging_folder_sink.<name>.writer_identity, in the logging project")
def sink_writer(plan):
    p = _platform(plan)
    grants = [g for g in p.resources("google_project_iam_member") if g.get("role") == "roles/logging.bucketWriter"]
    require(grants, "No roles/logging.bucketWriter grant - the sink would silently drop every entry")
    require(any(g.references_type("google_logging_folder_sink", "member") for g in grants),
            "The bucketWriter grant must go to the sink's writer_identity")


@requirement("R23.8", "Guardrails are set once, on the Meridian folder, and inherited",
             hint="google_org_policy_policy with parent = the Meridian folder: compute.skipDefaultNetworkCreation, iam.disableServiceAccountKeyCreation")
def guardrails(plan):
    p = _platform(plan)
    on_top = set()
    for pol in p.resources("google_org_policy_policy"):
        if _on_top(p, pol, "parent"):
            name = str(p.source and pol.config.get("expressions", {}).get("name", {}).get("constant_value") or "")
            on_top.add(pol.index if isinstance(pol.index, str) else name.rsplit("/", 1)[-1])
    missing = GUARDRAILS - on_top
    require(not missing, f"Missing on the Meridian folder: {sorted(missing)}")


@requirement("R23.9", "Access is granted on folders: the platform team on Meridian, developers on dev only",
             hint="google_folder_iam_member: roles/resourcemanager.folderAdmin for the platform group on Meridian; developer roles only on the dev folder")
def folder_iam(plan):
    p = _platform(plan)
    top = _top(p)
    dev = [f for f in _children(p, top) if f.get("display_name") == "dev"]
    require(dev, "No dev folder")
    members = p.resources("google_folder_iam_member")
    admin = [m for m in members if m.get("role") == "roles/resourcemanager.folderAdmin" and _on_top(p, m, "folder")]
    require(admin, "The platform group has no folderAdmin on the Meridian folder")
    devs = p.variable_value("developer_group")
    leaks = [f"{m.get('role')} on {[f.get('display_name') for f in p.linked(m, 'google_folder', 'folder')]}"
             for m in members if devs and str(m.get("member")) == f"group:{devs}"
             and dev[0] not in p.linked(m, "google_folder", "folder")]
    require(not leaks, f"Developers have access outside the dev folder: {leaks}")
    org = p.resources("google_organization_iam_member") + p.resources("google_organization_iam_binding")
    require(not org, "Avoid organization-level grants here: every one of them applies to the whole company")


@requirement("R23.10", "The existing environments don't change",
             hint="The landing zone is a new root (envs/platform); dev and prod are untouched")
def untouched(plan):
    changed = [f"{r.address} ({'/'.join(r.actions)})" for r in plan.all_changes() if r.actions not in (["no-op"], ["read"])]
    require(not changed, "dev would change:\n  " + "\n  ".join(changed[:10]))


# ------------------------------------------------------------------ challenge
@requirement("C23.1", "Security and billing notices reach real people",
             hint='google_essential_contacts_contact on the Meridian folder for SECURITY and BILLING', level="challenge")
def contacts(plan):
    p = _platform(plan)
    cats = set()
    for c in p.resources("google_essential_contacts_contact"):
        if _on_top(p, c, "parent"):
            cats |= set(c.get("notification_category_subscriptions") or [])
    missing = {"SECURITY", "BILLING"} - cats
    require(not missing, f"No essential contact on the Meridian folder for {sorted(missing)}")


@requirement("C23.2", "Data stays in US locations",
             hint='gcp.resourceLocations on the Meridian folder: allowed_values = ["in:us-locations"]', level="challenge")
def locations(plan):
    p = _platform(plan)
    # The policy name embeds the folder ID (unknown until apply): find the block in the source.
    names = {b.labels[1] for b in p.source.blocks("resource", "google_org_policy_policy") if "gcp.resourceLocations" in b.body}
    pols = [x for x in p.resources("google_org_policy_policy") if _on_top(p, x, "parent") and x.name in names]
    require(pols, "No gcp.resourceLocations policy on the Meridian folder")
    rules = ((pols[0].get("spec") or [{}])[0].get("rules") or [])
    allowed = [v for r in rules for blk in (r.get("values") or []) for v in (blk.get("allowed_values") or [])]
    require(allowed and all(v.startswith("in:us") or v.startswith("us") for v in allowed), f"Allowed locations: {allowed or 'none'}")


@requirement("C23.3", "Noisy, rarely-read logs stay out of the central bucket",
             hint="exclusions { name = ..., filter = load balancer requests below 400 } on the folder sink", level="challenge")
def exclusions(plan):
    p = _platform(plan)
    s = p.resources("google_logging_folder_sink")
    require(s and s[0].blocks("exclusions"), "The folder sink has no exclusions")
    require(any("load_balancer" in str(e.get("filter")) for e in s[0].blocks("exclusions")),
            "Exclude the load balancer request logs (the bulk of the volume)")


@requirement("C23.4", "The factory rejects names that would make an invalid project ID",
             hint="validation: length(name) <= 25 (ID = name + '-' + 4 hex chars, max 30); tests/challenge/modules/project-factory must pass",
             level="challenge",
             test="id_length.tftest.hcl")
def id_length(plan):
    var = next(iter(plan.source.blocks("variable", "projects", under="modules/project-factory")), None)
    require(var is not None and any("length(" in v.body and "keys(var.projects)" in v.body for v in var.blocks("validation")),
            "No validation on project name length in modules/project-factory")
