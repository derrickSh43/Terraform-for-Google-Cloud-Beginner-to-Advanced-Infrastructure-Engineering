"""Lesson 01 - Terraform Basics: requirement checks.

Checks inspect the *plan*, so any correct way of writing the HCL passes.
"""

from coursekit.checks import one, require, requirement


def _bucket(plan):
    return one(plan, "google_storage_bucket", "Cloud Storage bucket")


# ------------------------------------------------------------------ lab
@requirement("R1.1", "Google provider is declared and version-pinned",
             hint='In required_providers: google = { source = "hashicorp/google", version = "~> 8.12" }')
def provider_pinned(plan):
    cfg = plan.provider_config("google")
    require(cfg.get("full_name", "").endswith("hashicorp/google"), "The hashicorp/google provider is not declared")
    constraint = plan.provider_constraint("google")
    require(constraint, "The google provider has no version constraint, so any future version could be installed")
    require(">=" not in constraint or "<" in constraint,
            f"Constraint '{constraint}' has no upper bound; use a pessimistic constraint like \"~> 8.12\"")


@requirement("R1.2", "Provider project and region come from variables",
             hint="provider \"google\" { project = var.project_id  region = var.region }")
def provider_uses_vars(plan):
    require("var.project_id" in plan.provider_references("google", "project"),
            "provider \"google\" does not set project = var.project_id (hard-coded values break reuse)")
    require("var.region" in plan.provider_references("google", "region"),
            "provider \"google\" does not set region = var.region")


@requirement("R1.3", "Input variables are declared with descriptions",
             hint="Each variable block needs a description; project_id must not have a default.")
def variables_declared(plan):
    v = plan.variables()
    for name in ("project_id", "region"):
        require(name in v, f"variable \"{name}\" is not declared")
        require(v[name].get("description"), f"variable \"{name}\" has no description")
    require("default" not in v["project_id"], "project_id should be required (no default) so each environment must set it")


@requirement("R1.4", "Exactly one bucket, named after the project",
             hint='Build the name from the variable, e.g. name = "${var.project_id}-assets"')
def bucket_named(plan):
    b = _bucket(plan)
    project = plan.variable_value("project_id") or ""
    if b.is_unknown("name"):
        refs = b.references("name")
        require("var.project_id" in refs or any(r.startswith("local.") for r in refs),
                "Bucket name does not include var.project_id")
    else:
        require(project and project in b.get("name", ""),
                f"Bucket name '{b.get('name')}' does not include the project ID '{project}' (bucket names are global)")


@requirement("R1.5", "Bucket blocks public access",
             hint='Set uniform_bucket_level_access = true and public_access_prevention = "enforced".')
def bucket_private(plan):
    b = _bucket(plan)
    require(b.get("uniform_bucket_level_access") is True, "uniform_bucket_level_access is not true")
    require(b.get("public_access_prevention") == "enforced",
            f"public_access_prevention is '{b.get('public_access_prevention', 'inherited')}', expected 'enforced'")


@requirement("R1.6", "Object versioning is enabled",
             hint="Add a versioning { enabled = true } block.")
def bucket_versioned(plan):
    b = _bucket(plan)
    blocks = b.blocks("versioning")
    require(blocks and blocks[0].get("enabled") is True, "versioning is not enabled")


@requirement("R1.7", "Bucket carries the standard Meridian labels",
             hint='labels = { app = "meridian", env = var.environment, managed_by = "terraform" }')
def bucket_labels(plan):
    b = _bucket(plan)
    labels = b.get("labels") or {}
    for key in ("app", "env", "managed_by"):
        require(key in labels, f"label '{key}' is missing (found: {sorted(labels) or 'none'})")
    require(labels.get("app") == "meridian", f"label app should be 'meridian', got '{labels.get('app')}'")
    require(labels.get("managed_by") == "terraform", f"label managed_by should be 'terraform', got '{labels.get('managed_by')}'")
    require("environment" in plan.variables(), "variable \"environment\" is not declared")
    require(labels.get("env") == plan.variable_value("environment"), "label env should come from var.environment")


@requirement("R1.8", "Outputs expose the bucket name and URL",
             hint="output \"bucket_name\" { value = google_storage_bucket.<name>.name } - same idea for bucket_url.")
def outputs(plan):
    outs = plan.outputs()
    for name, attr in (("bucket_name", "name"), ("bucket_url", "url")):
        require(name in outs, f"output \"{name}\" is not defined")
        refs = plan.output_references(name)
        require(any(r.startswith("google_storage_bucket.") and r.endswith("." + attr) for r in refs),
                f"output \"{name}\" should reference the bucket's .{attr} attribute")


@requirement("R1.9", "A data source reports the active project",
             hint='data "google_client_config" "current" {}  then output "active_project" uses .project')
def data_source(plan):
    require(plan.data_sources("google_client_config"), "No google_client_config data source declared")
    require("active_project" in plan.outputs(), "output \"active_project\" is not defined")
    refs = plan.output_references("active_project")
    require(any(r.startswith("data.google_client_config.") for r in refs),
            "output \"active_project\" should read from the google_client_config data source")


# ------------------------------------------------------------------ challenge
@requirement("C1.1", "Bucket name gets a random suffix from the random provider",
             hint='Add hashicorp/random to required_providers, create random_id, use its .hex in the name.',
             level="challenge")
def random_suffix(plan):
    require(plan.resources("random_id"), "No random_id resource found")
    require(plan.provider_constraint("random"), "hashicorp/random is not version-pinned in required_providers")
    require(_bucket(plan).references_type("random_id", "name"), "The bucket name does not use the random_id")


@requirement("C1.2", "Noncurrent object versions expire",
             hint="lifecycle_rule { condition { days_since_noncurrent_time = 30 } action { type = \"Delete\" } }",
             level="challenge")
def lifecycle(plan):
    rules = _bucket(plan).blocks("lifecycle_rule")
    require(rules, "The bucket has no lifecycle_rule")
    for rule in rules:
        action = (rule.get("action") or [{}])[0]
        cond = (rule.get("condition") or [{}])[0]
        days = cond.get("days_since_noncurrent_time") or cond.get("num_newer_versions")
        if action.get("type") == "Delete" and days and int(days) <= 90:
            return
    require(False, "No lifecycle rule deletes noncurrent versions within 90 days")


@requirement("C1.3", "Labels are defined once in a local value",
             hint="locals { common_labels = { ... } } then labels = local.common_labels",
             level="challenge")
def labels_local(plan):
    refs = _bucket(plan).references("labels")
    require(any(r.startswith("local.") for r in refs), "The bucket's labels do not come from a local value")


@requirement("C1.4", "Bucket is single-region STANDARD storage in var.region",
             hint='storage_class = "STANDARD" and location = upper(var.region) keeps costs predictable.',
             level="challenge")
def location(plan):
    b = _bucket(plan)
    region = (plan.variable_value("region") or "").upper()
    require(str(b.get("location", "")).upper() == region,
            f"Bucket location is '{b.get('location')}', expected the single region '{region}'")
    require(b.get("storage_class", "STANDARD") == "STANDARD", f"storage_class is '{b.get('storage_class')}'")
