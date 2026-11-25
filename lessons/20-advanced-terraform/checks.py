"""Lesson 20 - Advanced Terraform Engineering.

`plan` is dev against the deployed environment: lesson 19 plus the reporting team's legacy file,
with one label added by hand in the console (drift). Import blocks are resolved offline against
state/dev.cloud.json (see coursekit/cloudsim.py).
"""

import re

from coursekit.checks import require, requirement

MOD = "modules/reporting"
LEGACY = {
    "google_service_account.reporter": "module.reporting.google_service_account.reporter",
    "google_storage_bucket.reports": "module.reporting.google_storage_bucket.reports",
    "google_storage_bucket_iam_member.reporter_writes": "module.reporting.google_storage_bucket_iam_member.reporter_writes",
}
TOPIC_OLD = "google_pubsub_topic.report_ready"
TOPIC_NEW = "module.reporting.google_pubsub_topic.report_ready"
ARCHIVE = "module.reporting.google_storage_bucket.archive"
ARCHIVE_ID = "meridian-dev-report-archive"
EXPORTS = {f'module.reporting.google_storage_bucket.exports["{q}"]': f"meridian-dev-export-{q}" for q in ("2025-q3", "2025-q4")}
REPORTING_TYPES = ("google_service_account", "google_storage_bucket", "google_storage_bucket_iam_member", "google_pubsub_topic")


def _call(plan, name="reporting"):
    return plan.module_calls().get(name)


def _diff(plan, address):
    r = plan.resource(address)
    if r is None:
        return f"{address} is not in the plan"
    if r.actions == ["no-op"]:
        return ""
    attrs = plan.changed_attributes(address)
    return f"{address} would be {'/'.join(r.actions)}" + (f" (differs in: {', '.join(attrs)})" if attrs and r.actions == ["update"] else "")


def _mod_text(plan):
    return {n: t for n, t in plan.source.files.items() if n.startswith(MOD + "/") and n.endswith(".tf")}


def _lifecycle_true(block, setting):
    lc = block.block("lifecycle")
    return bool(lc and (lc.attr(setting) or "").strip().lower() == "true")


# ------------------------------------------------------------------ lab
@requirement("R20.1", "The reporting resources live in a reusable module that states its provider range",
             hint='modules/reporting (main/variables/outputs/versions.tf); module "reporting" in envs/dev; '
                  "versions.tf with required_providers google; envs/dev/legacy_reporting.tf deleted")
def module_exists(plan):
    call = _call(plan)
    require(call, 'envs/dev has no module "reporting"')
    require(str(call.get("source", "")).rstrip("/").endswith("modules/reporting"),
            f'module "reporting" must use ../../modules/reporting (source = {call.get("source")!r})')
    tf_blocks = plan.source.blocks("terraform", under=MOD, recursive=False)
    providers = [b for t in tf_blocks for b in t.children if b.type == "required_providers"]
    require(providers and "google" in providers[0].body,
            "modules/reporting doesn't declare required_providers { google = ... } - a module should state the provider range it supports")
    left = [f"{b.labels[0]}.{b.labels[1]} ({b.file})" for b in plan.source.blocks("resource", under=plan.root, recursive=False)
            if b.labels and b.labels[0] in REPORTING_TYPES]
    require(not left, "Reporting resources are still defined in the dev root: " + ", ".join(left))


@requirement("R20.2", "Every legacy resource was moved to its new address, not recreated",
             hint="moved { from = google_storage_bucket.reports  to = module.reporting.google_storage_bucket.reports } - one per resource, in envs/dev")
def moved(plan):
    wanted = dict(LEGACY)
    if not plan.resource(TOPIC_OLD) or plan.resource(TOPIC_OLD).actions != ["forget"]:
        wanted[TOPIC_OLD] = TOPIC_NEW            # the challenge hands the topic over instead
    bad = []
    for old, new in wanted.items():
        r = plan.resource(new)
        if r is None:
            bad.append(f"{new} is missing (expected the deployed {old} to move there)")
        elif r.previous_address != old:
            bad.append(f"{new} is not moved from {old}: plan says {'/'.join(r.actions)}"
                       + (" - a new object with the same name would fail to create, and the old one would be deleted" if "create" in r.actions else ""))
    require(not bad, "\n  ".join(bad))
    require(plan.source.blocks("moved", under=plan.root, recursive=False),
            "No moved blocks in envs/dev - cross-module moves are declared in the calling (root) module")


@requirement("R20.3", "Deployed dev changes safely: nothing destroyed or replaced",
             hint="A refactor changes addresses, not objects. Plan: 0 to destroy.")
def safe(plan):
    bad = [f"{r.address} would be {'REPLACED' if r.is_replaced else 'DESTROYED'}" +
           (f" (forced by: {', '.join('.'.join(map(str, p)) for p in r.replace_paths)})" if r.is_replaced else "")
           for r in plan.all_changes() if r.is_replaced or r.actions == ["delete"]]
    require(not bad, "Against the deployed dev environment:\n  " + "\n  ".join(bad))


@requirement("R20.4", "The module hard-codes nothing environment-specific",
             hint="project, names and labels come from variables (var.project_id, var.name_prefix, var.labels)")
def reusable(plan):
    texts = _mod_text(plan)
    require(texts, "modules/reporting has no .tf files")
    found = sorted({m for t in texts.values() for m in re.findall(r'"(meridian-(?:dev|prod)[^"]*)"', re.sub(r"(?m)#.*$", "", t))})
    require(not found, f"modules/reporting contains environment-specific literals: {found}")
    call = _call(plan) or {}
    keys = set((call.get("expressions") or {}).keys())
    require({"project_id", "name_prefix"} <= keys, "Pass project_id and name_prefix to the module from envs/dev")


@requirement("R20.5", "The hand-made archive bucket is imported, not recreated",
             hint=f'import {{ to = {ARCHIVE}  id = "{ARCHIVE_ID}" }} in envs/dev, plus a matching resource in the module')
def imported(plan):
    r = plan.resource(ARCHIVE)
    require(r, f"{ARCHIVE} is not in the plan - add the resource to modules/reporting")
    require(ARCHIVE in plan.imported,
            f"{ARCHIVE} is not imported (plan says {'/'.join(r.actions)}): creating {ARCHIVE_ID} would fail - the name is taken")


@requirement("R20.6", "The imported bucket's configuration matches the real bucket",
             hint="After an import the plan must show no changes for it: storage class, location, labels and lifecycle as in the cloud (see lab.md)")
def import_matches(plan):
    require(ARCHIVE in plan.imported, f"{ARCHIVE} wasn't imported")
    d = _diff(plan, ARCHIVE)
    require(not d, d + " - the configuration doesn't describe the bucket as it exists; applying would change it")


@requirement("R20.7", "A pure refactor: moved resources show no changes, and the console label is kept",
             hint='The console added labels "cost-center" = "analytics" to the reports bucket. Finance wants it: add it to the configuration (don\'t revert it).')
def no_changes(plan):
    diffs = [d for d in (_diff(plan, a) for a in LEGACY.values()) if d]
    require(not diffs, "\n  ".join(diffs))
    labels = (plan.resource(LEGACY["google_storage_bucket.reports"]).get("labels") or {})
    require(labels.get("cost-center") == "analytics", "The reports bucket lost its cost-center label")


@requirement("R20.8", "A check block guards the reporting buckets, and it passes",
             hint='check "..." { assert { condition = google_storage_bucket.reports.uniform_bucket_level_access ... } } in modules/reporting')
def check_block(plan):
    checks = plan.source.blocks("check", under=MOD)
    require(checks, "modules/reporting has no check block")
    require(any("google_storage_bucket." in c.body for c in checks), "The check block doesn't assert anything about the buckets")
    results = [c for c in plan.check_results() if c["address"].startswith("module.reporting.")]
    require(results, "The plan has no check results for module.reporting")
    failed = [f"{c['address']}: {'; '.join(c['messages']) or c['status']}" for c in results if c["status"] == "fail"]
    require(not failed, "Failing check(s) - the deployed reality breaks your post-condition:\n  " + "\n  ".join(failed))


@requirement("R20.9", "The module refuses retention outside 30-365 days",
             hint="variable \"retention_days\" with a validation block; tests/lab/modules/reporting must pass")
def validation(plan):
    var = next((b for b in plan.source.blocks("variable", "retention_days", under=MOD)), None)
    require(var, 'modules/reporting has no variable "retention_days"')
    require(var.block("validation"), "retention_days has no validation block")
    call = _call(plan) or {}
    require("retention_days" in (call.get("expressions") or {}), "envs/dev should set retention_days explicitly")


@requirement("R20.10", "prod gets the same reporting module (created fresh, nothing to move or import)",
             hint='module "reporting" in envs/prod with the prod project and name prefix; no moved/import blocks needed there')
def prod(plan):
    prod = plan.others["prod"]
    require(_call(prod), 'envs/prod has no module "reporting"')
    project = prod.variable_value("project_id")
    buckets = [b for b in prod.resources("google_storage_bucket") if b.module == "module.reporting"]
    require(len(buckets) >= 2, "prod's reporting module should create the reports and archive buckets")
    wrong = [b.address for b in buckets if b.get("project") != project or "prod" not in str(b.get("name"))]
    require(not wrong, f"prod reporting buckets must be in {project} with prod names: {wrong}")


# ------------------------------------------------------------------ challenge
@requirement("C20.1", "The report-ready topic is handed to the events team without deleting it",
             hint="removed { from = google_pubsub_topic.report_ready  lifecycle { destroy = false } } and the topic gone from the module",
             level="challenge")
def handed_over(plan):
    r = plan.resource(TOPIC_OLD) or plan.resource(TOPIC_NEW)
    require(r is not None, "The deployed topic is not in the plan at all")
    require(r.actions == ["forget"], f"{r.address} would be {'/'.join(r.actions)} - expected Terraform to forget it (removed block, destroy = false)")
    require(not plan.others["prod"].resources("google_pubsub_topic") or
            not any(t.module == "module.reporting" for t in plan.others["prod"].resources("google_pubsub_topic")),
            "The reporting module still creates the topic (prod would get one)")


@requirement("C20.2", "The auditors' quarterly export buckets are imported with one for_each import block",
             hint='import { for_each = toset(["2025-q3", "2025-q4"])  to = module.reporting.google_storage_bucket.exports[each.key]  id = "meridian-dev-export-${each.key}" }',
             level="challenge")
def exports(plan):
    missing = [a for a in EXPORTS if a not in plan.imported]
    require(not missing, f"Not imported: {missing}")
    diffs = [d for d in (_diff(plan, a) for a in EXPORTS) if d]
    require(not diffs, "\n  ".join(diffs))
    blocks = plan.source.blocks("import", under=plan.root, recursive=False)
    require(any(b.attr("for_each") for b in blocks), "Use a single import block with for_each instead of one block per bucket")


@requirement("C20.3", "Adopted archives can't be destroyed by accident",
             hint="lifecycle { prevent_destroy = true } on the archive and export buckets", level="challenge")
def protected(plan):
    res = {b.labels[1]: b for b in plan.source.blocks("resource", "google_storage_bucket", under=MOD)}
    bad = [n for n in ("archive", "exports") if n not in res or not _lifecycle_true(res[n], "prevent_destroy")]
    require(not bad, f"Missing prevent_destroy on: {bad}")


@requirement("C20.4", "The module validates export quarters",
             hint='variable "export_quarters" (list(string)) with validation ^20NN-q[1-4]$; tests/challenge/modules/reporting must pass',
             level="challenge",
             test="exports.tftest.hcl")
def quarter_validation(plan):
    var = next((b for b in plan.source.blocks("variable", "export_quarters", under=MOD)), None)
    require(var and var.block("validation"), 'modules/reporting needs variable "export_quarters" with a validation block')
