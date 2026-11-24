"""Lesson 10 - Identity and Access Management.

`plan` is dev against the deployed environment *including* the audited
legacy-access.tf (state/dev.tfstate). coursekit.iam builds the effective
grant list from the plan, so checks reason about who can do what.
"""

from coursekit import iam
from coursekit.checks import require, requirement

CI_ACCOUNT_ID = "meridian-ci"
WORKLOAD_ROLES = {"roles/logging.logWriter", "roles/monitoring.metricWriter"}
RISKY_PREFIXES = ("iam.", "resourcemanager.")
STORAGE_OBJECT_ROLES = {"roles/storage.objectAdmin", "roles/storage.objectCreator", "roles/storage.objectUser"}
IMPERSONATION_ROLES = {"roles/iam.serviceAccountTokenCreator", "roles/iam.serviceAccountUser"}


def _sa(plan, account_id):
    sas = [s for s in plan.resources("google_service_account") if s.get("account_id") == account_id]
    require(len(sas) == 1, f'Expected one service account "{account_id}", found {len(sas)}')
    return sas[0]


def _ci(plan):
    return _sa(plan, CI_ACCOUNT_ID)


def _human(g):
    return g.kind in ("user", "group", "domain")


# ------------------------------------------------------------------ lab
@requirement("R10.1", "No service account keys, and nothing outputs one",
             hint="Delete google_service_account_key and its output. Humans impersonate; CI uses impersonation or Workload Identity Federation.")
def no_keys(plan):
    keys = plan.resources("google_service_account_key")
    require(not keys, "Service account keys still exist: " + ", ".join(k.address for k in keys) +
            " - a leaked JSON key is a permanent credential")
    leaking = [n for n in plan.outputs() if any("google_service_account_key" in r for r in plan.output_references(n))]
    require(not leaking, f"Outputs expose key material: {leaking}")


@requirement("R10.2", "No basic roles, and no individual users at project level",
             hint="Basic roles (owner/editor/viewer) are far too broad. Grant humans predefined roles through groups.")
def no_basic_no_users(plan):
    grants = iam.grants(plan)
    basic = [f"{g.role} -> {g.principal} ({g.source.address})" for g in grants if g.is_basic]
    require(not basic, "Basic roles granted:\n  " + "\n  ".join(basic))
    users = [f"{g.principal} has {g.role}" for g in grants if g.scope == "project" and g.kind == "user"]
    require(not users, "Individual users hold project roles (they leave, change teams, lose laptops):\n  " + "\n  ".join(users))


@requirement("R10.3", "No authoritative project IAM",
             hint="google_project_iam_binding / _policy own the whole member list and silently remove other grants. Use _member.")
def no_authoritative(plan):
    found = plan.resources("google_project_iam_binding") + plan.resources("google_project_iam_policy")
    require(not found, "Authoritative IAM still present: " + ", ".join(r.address for r in found))


@requirement("R10.4", "CI uses a custom role with an explicit, minimal permission list",
             hint="google_project_iam_custom_role with a short permissions list (no wildcards, no iam.*/resourcemanager.*, no setIamPolicy) granted to meridian-ci")
def ci_custom_role(plan):
    ci = _ci(plan)
    grants = iam.for_principal(iam.grants(plan), f"sa:{ci.address}", "project")
    require(grants, "meridian-ci has no project-level role: CI could not roll out the web MIG")
    for g in grants:
        perms = iam.custom_role_permissions(plan, g)
        require(perms is not None, f"meridian-ci holds predefined role {g.role} at project level - use a custom role with only what CI needs")
        require(0 < len(perms) <= 15, f"The custom role has {len(perms)} permissions - keep it to what CI actually does (<= 15)")
        bad = [p for p in perms if "*" in p or p.endswith(".setIamPolicy") or p.startswith(RISKY_PREFIXES)]
        require(not bad, f"Risky permissions in the CI role: {bad}")
    roles = plan.resources("google_project_iam_custom_role")
    require(all(r.get("stage", "GA") == "GA" for r in roles), "Custom roles should be stage = \"GA\"")


@requirement("R10.5", "CI publishes assets through bucket-level IAM only",
             hint='google_storage_bucket_iam_member on the assets bucket (roles/storage.objectAdmin), not a project-wide storage role')
def ci_bucket_access(plan):
    ci = _ci(plan)
    all_grants = iam.grants(plan)
    mine = iam.for_principal(all_grants, f"sa:{ci.address}")
    bucket = [g for g in mine if g.scope == "bucket" and g.role in STORAGE_OBJECT_ROLES]
    require(bucket, "meridian-ci has no object role on a bucket")
    assets = [b for b in plan.resources("google_storage_bucket") if (b.get("name") or "").endswith("-assets")]
    require(any(g.target is not None and assets and g.target.address == assets[0].address or
                (assets and g.target_name == assets[0].get("name")) for g in bucket),
            "The bucket grant is not on the assets bucket")
    project_storage = [g.role for g in mine if g.scope == "project" and g.role.startswith("roles/storage.")]
    require(not project_storage, f"meridian-ci holds project-wide storage roles {project_storage}: that reaches every bucket")


@requirement("R10.6", "Humans impersonate CI instead of using keys, granted on the account itself",
             hint='google_service_account_iam_member on meridian-ci: role = "roles/iam.serviceAccountTokenCreator", member = a group')
def impersonation(plan):
    ci = _ci(plan)
    all_grants = iam.grants(plan)
    project_wide = [f"{g.principal} has {g.role}" for g in all_grants if g.scope == "project" and g.role in IMPERSONATION_ROLES]
    require(not project_wide, "Project-level impersonation roles let principals act as EVERY service account "
                              "(including meridian-web and meridian-app):\n  " + "\n  ".join(project_wide))
    on_ci = [g for g in all_grants if g.scope == "service_account" and g.target is not None and g.target.address == ci.address
             and g.role == "roles/iam.serviceAccountTokenCreator"]
    require(on_ci, "Nobody can impersonate meridian-ci - grant roles/iam.serviceAccountTokenCreator on the account")
    require(all(g.kind == "group" for g in on_ci), "Impersonation should be granted to groups, not individuals: " +
            ", ".join(g.principal for g in on_ci if g.kind != "group"))


@requirement("R10.7", "Developers get read-only access through groups",
             hint='modules/project-access: group:... => ["roles/compute.viewer", "roles/logging.viewer"]')
def developer_groups(plan):
    grants = [g for g in iam.grants(plan) if g.scope == "project" and _human(g)]
    require(grants, "No group has any project access - developers can't read logs or see VMs")
    require(all(g.kind == "group" for g in grants), "Human access must go through groups")
    roles = {g.role for g in grants}
    require(any(r.endswith("Viewer") or r.endswith(".viewer") for r in roles), f"Developers should get viewer roles, got {sorted(roles)}")
    writes = [r for r in roles if not (r.endswith("viewer") or r.endswith("Viewer"))]
    require(not writes, f"dev developers get non-read roles {writes} - changes go through Terraform, not the console")


@requirement("R10.8", "Workload service accounts keep exactly their two roles",
             hint="web and app still need roles/logging.logWriter and roles/monitoring.metricWriter - via _member grants.")
def workloads(plan):
    all_grants = iam.grants(plan)
    for account in ("meridian-web", "meridian-app"):
        sa = _sa(plan, account)
        roles = {g.role for g in iam.for_principal(all_grants, f"sa:{sa.address}", "project")}
        require(roles == WORKLOAD_ROLES, f"{account} has project roles {sorted(roles)}, expected {sorted(WORKLOAD_ROLES)}"
                + (" - deleting the authoritative binding must not remove the web/app logWriter _member grants" if not roles else ""))


@requirement("R10.9", "The cleanup is safe: the CI account is kept, only bad grants and the key are removed",
             hint="moved { from = google_service_account.ci  to = module.ci.google_service_account.this }")
def safe_cleanup(plan):
    allowed_deletes = {"google_service_account_key", "google_project_iam_member", "google_project_iam_binding", "google_project_iam_policy"}
    bad = []
    for r in plan.all_changes():
        if r.is_replaced:
            why = ", ".join(".".join(str(x) for x in p) for p in r.replace_paths) or "a force-new attribute"
            bad.append(f"{r.address} would be REPLACED (forced by: {why})")
        elif r.actions == ["delete"] and r.type not in allowed_deletes:
            bad.append(f"{r.address} would be DESTROYED")
    require(not bad, "Against the deployed dev environment:\n  " + "\n  ".join(bad) +
            ("\n  (the CI account is referenced by the CI system - recreating it changes its unique ID)"
             if any("google_service_account" in b for b in bad) else ""))
    ci = _ci(plan)
    require(ci.actions in (["no-op"], ["update"]), f"meridian-ci would be {ci.actions} - move it instead")


@requirement("R10.10", "prod gets the same identities, with tighter human access",
             hint="Same module calls in prod; prod developers get at most what dev developers get.")
def prod(plan):
    prod = plan.others["prod"]
    srcs = lambda p: {n: c.get("source") for n, c in p.configuration.get("root_module", {}).get("module_calls", {}).items()}
    require(srcs(plan) == srcs(prod), "dev and prod call different modules")
    require(prod.resources("google_project_iam_custom_role"), "prod has no CI custom role")
    dev_h = {g.role for g in iam.grants(plan) if g.scope == "project" and _human(g)}
    prod_h = {g.role for g in iam.grants(prod) if g.scope == "project" and _human(g)}
    require(prod_h and prod_h <= dev_h, f"prod human roles {sorted(prod_h)} should be a non-empty subset of dev's {sorted(dev_h)}")
    require(not prod.resources("google_service_account_key"), "prod must not have service account keys")


# ------------------------------------------------------------------ challenge
@requirement("C10.1", "GitHub Actions authenticates with Workload Identity Federation, limited to one repository",
             hint="Pool + OIDC provider (token.actions.githubusercontent.com) with attribute_condition on assertion.repository, "
                  "and roles/iam.workloadIdentityUser on meridian-ci for that repository's principalSet",
             level="challenge")
def wif(plan):
    providers = plan.resources("google_iam_workload_identity_pool_provider")
    require(providers, "No google_iam_workload_identity_pool_provider")
    p = providers[0]
    require((p.get("oidc.0.issuer_uri") or "") == "https://token.actions.githubusercontent.com", "The provider must trust GitHub's OIDC issuer")
    cond = p.get("attribute_condition") or ""
    require("assertion.repository" in cond, "attribute_condition must restrict which repository may authenticate - "
                                            "without it, ANY GitHub repository's workflow could impersonate CI")
    require("attribute.repository" in (p.get("attribute_mapping") or {}), "Map attribute.repository so the principalSet can use it")
    ci = _ci(plan)
    wiu = [g for g in iam.grants(plan) if g.scope == "service_account" and g.target is not None and g.target.address == ci.address
           and g.role == "roles/iam.workloadIdentityUser"]
    require(wiu, "No roles/iam.workloadIdentityUser grant on meridian-ci")
    require(all(g.principal.startswith("principalSet") for g in wiu), "Grant workloadIdentityUser to the pool's principalSet")
    member_src = wiu[0].source.references("member")
    require(wiu[0].source.get("member") is None and any("google_iam_workload_identity_pool" in r for r in member_src) or
            "attribute.repository/" in (wiu[0].source.get("member") or ""),
            "The principalSet must be scoped to attribute.repository/<owner/repo>, not the whole pool")


@requirement("C10.2", "Human access expires",
             hint='condition { expression = "request.time < timestamp(\\"2027-06-30T00:00:00Z\\")" } on group grants', level="challenge")
def expiring(plan):
    human = [g for g in iam.grants(plan) if g.scope == "project" and _human(g)]
    require(human, "No human grants found")
    for g in human:
        expr = (g.condition or {}).get("expression", "")
        require("request.time" in expr and "<" in expr, f"{g.principal} {g.role} has no expiry condition")


@requirement("C10.3", "An organization policy blocks service account key creation in the project",
             hint="google_org_policy_policy for iam.disableServiceAccountKeyCreation with spec { rules { enforce = \"TRUE\" } }",
             level="challenge")
def org_policy(plan):
    pols = [p for p in plan.resources("google_org_policy_policy") if (p.get("name") or "").endswith("iam.disableServiceAccountKeyCreation")]
    require(pols, "No iam.disableServiceAccountKeyCreation policy")
    rules = pols[0].get("spec.0.rules") or []
    require(any(str(r.get("enforce", "")).upper() == "TRUE" for r in rules), "The policy must enforce = \"TRUE\"")


@requirement("C10.4", "The CI module refuses dangerous permissions",
             hint="validation on var.permissions; tests/challenge/ci_identity_module.tftest.hcl must pass", level="challenge")
def ci_validation(plan):
    mods = plan.configuration.get("root_module", {}).get("module_calls", {})
    require(any("permissions" in m.get("module", {}).get("variables", {}) for m in mods.values()), "No module declares var.permissions")
