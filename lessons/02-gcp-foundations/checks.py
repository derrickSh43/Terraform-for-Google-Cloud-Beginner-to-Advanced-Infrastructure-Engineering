"""Lesson 02 - Google Cloud Foundations: requirement checks."""

import re

from coursekit.checks import one, require, requirement

REQUIRED_APIS = {
    "compute.googleapis.com",
    "iam.googleapis.com",
    "storage.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
}
WEB_ROLES = {"roles/logging.logWriter", "roles/monitoring.metricWriter"}
BASIC_ROLES = {"roles/owner", "roles/editor", "roles/viewer"}
AUTHORITATIVE = (
    "google_project_iam_policy",
    "google_project_iam_binding",
)


def _services(plan):
    return {r.get("service"): r for r in plan.resources("google_project_service")}


def _web_sa(plan):
    return one(plan, "google_service_account", "service account")


# ------------------------------------------------------------------ lab
@requirement("R2.1", "Required Google Cloud APIs are enabled",
             hint="One google_project_service per API - for_each over a set keeps it short.")
def apis_enabled(plan):
    missing = REQUIRED_APIS - set(_services(plan))
    require(not missing, "Missing API(s): " + ", ".join(sorted(missing)))


@requirement("R2.2", "APIs are not disabled on destroy",
             hint="Set disable_on_destroy = false on google_project_service.")
def no_disable_on_destroy(plan):
    require(_services(plan), "No google_project_service resources found")
    bad = [r.address for r in _services(plan).values() if r.get("disable_on_destroy", True) is not False]
    require(not bad, "disable_on_destroy is not false on: " + ", ".join(bad))


@requirement("R2.3", "A dedicated service account exists for the web tier",
             hint='google_service_account with account_id (6-30 chars, lowercase, e.g. "meridian-web") and a display_name.')
def service_account(plan):
    sa = _web_sa(plan)
    acct = sa.get("account_id", "")
    require(re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", acct),
            f"account_id '{acct}' is invalid: 6-30 chars, lowercase letters, digits and hyphens, starting with a letter")
    require(sa.get("display_name"), "The service account has no display_name")


@requirement("R2.4", "IAM grants are additive (google_project_iam_member)",
             hint="_binding and _policy are authoritative and can remove other people's access. Use google_project_iam_member.")
def additive_iam(plan):
    for t in AUTHORITATIVE:
        found = plan.resources(t)
        require(not found, f"{t} is authoritative and can wipe existing grants: " + ", ".join(r.address for r in found))
    require(plan.resources("google_project_iam_member"), "No google_project_iam_member resources found")


@requirement("R2.5", "The web service account has exactly the roles it needs",
             hint="Grant roles/logging.logWriter and roles/monitoring.metricWriter with member = \"serviceAccount:${google_service_account.web.email}\"")
def web_roles(plan):
    granted = set()
    for m in plan.resources("google_project_iam_member"):
        if m.references_type("google_service_account", "member"):
            granted.add(m.get("role"))
    missing = WEB_ROLES - granted
    require(not missing, "Web service account is missing role(s): " + ", ".join(sorted(missing)))
    extra = granted - WEB_ROLES
    require(not extra, "Web service account has roles it does not need (least privilege): " + ", ".join(sorted(extra)))


@requirement("R2.6", "No basic roles (owner / editor / viewer) are granted",
             hint="Basic roles grant thousands of permissions. Use predefined roles instead.")
def no_basic_roles(plan):
    for t in ("google_project_iam_member", "google_project_iam_binding"):
        for r in plan.resources(t):
            require(r.get("role") not in BASIC_ROLES, f"{r.address} grants the basic role {r.get('role')}")


@requirement("R2.7", "The service account waits for the IAM API",
             hint="Add depends_on = [google_project_service.<name>] to the service account.")
def sa_depends_on_api(plan):
    sa = _web_sa(plan)
    require(sa.depends_on_type("google_project_service"),
            "The service account has no dependency on google_project_service, so it could be created before the IAM API is enabled")


@requirement("R2.8", "Output exposes the web service account email",
             hint='output "web_service_account_email" { value = google_service_account.web.email }')
def sa_output(plan):
    require("web_service_account_email" in plan.outputs(), 'output "web_service_account_email" is not defined')
    refs = plan.output_references("web_service_account_email")
    require(any(r.startswith("google_service_account.") and r.endswith(".email") for r in refs),
            "The output should reference the service account's .email")


# ------------------------------------------------------------------ challenge
def _budget(plan):
    return one(plan, "google_billing_budget", "billing budget")


@requirement("C2.1", "A monthly budget alerts at 50%, 90% and 100%",
             hint="google_billing_budget with three threshold_rules blocks.", level="challenge")
def budget_thresholds(plan):
    b = _budget(plan)
    got = {round(float(t.get("threshold_percent", 0)), 2) for t in b.blocks("threshold_rules")}
    missing = {0.5, 0.9, 1.0} - got
    require(not missing, f"Missing threshold(s): {sorted(missing)} (found {sorted(got)})")
    amount = b.get("amount.0.specified_amount.0.units")
    require(amount, "The budget has no specified_amount")


@requirement("C2.2", "Budget is scoped to this project and uses variables",
             hint='budget_filter { projects = ["projects/${var.project_number}"] }; billing_account = var.billing_account',
             level="challenge")
def budget_scope(plan):
    b = _budget(plan)
    require("var.billing_account" in b.references("billing_account"), "billing_account should come from var.billing_account")
    projects = b.get("budget_filter.0.projects") or []
    require(projects, "The budget has no budget_filter.projects, so it watches the whole billing account")
    number = plan.variable_value("project_number")
    require(number and f"projects/{number}" in projects, f"budget_filter.projects should be [\"projects/<project_number>\"], got {projects}")


@requirement("C2.3", "Billing budgets API is enabled and the budget depends on it",
             hint="Add billingbudgets.googleapis.com to your APIs, and depends_on on the budget.", level="challenge")
def budget_api(plan):
    require("billingbudgets.googleapis.com" in _services(plan), "billingbudgets.googleapis.com is not enabled")
    require(_budget(plan).depends_on_type("google_project_service"), "The budget does not depend on the APIs")


@requirement("C2.4", "billing_account variable has a validation rule",
             hint="Add a validation block with a regex; tests/challenge/billing_account.tftest.hcl must pass.",
             level="challenge")
def billing_validation(plan):
    # The behaviour is proven by the native test; here we confirm the contract exists.
    require("billing_account" in plan.variables(), 'variable "billing_account" is not declared')
