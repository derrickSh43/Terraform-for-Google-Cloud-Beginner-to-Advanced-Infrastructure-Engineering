"""Lesson 19 - Advanced Security Engineering.

`plan` is dev against the deployed lesson 18 environment.
"""

import re

from coursekit import iam
from coursekit.checks import require, requirement

STORAGE_AGENT = re.compile(r"^serviceAccount:service-\d+@gs-project-accounts\.iam\.gserviceaccount\.com$")
GUARDRAILS = {
    "compute.vmExternalIpAccess": "deny_all",
    "storage.uniformBucketLevelAccess": "enforce",
    "sql.restrictPublicIp": "enforce",
    "iam.disableServiceAccountKeyCreation": "enforce",
}


def _key(plan):
    keys = plan.resources("google_kms_crypto_key")
    require(len(keys) == 1, f"Expected one Cloud KMS crypto key, found {len(keys)}")
    return keys[0]


def _secs(v):
    m = re.match(r"(\d+)s$", str(v or ""))
    return int(m.group(1)) if m else 0


def _policy(plan):
    p = plan.resources("google_compute_security_policy")
    require(len(p) == 1, f"Expected one Cloud Armor security policy, found {len(p)}")
    return p[0]


def _rules(policy):
    return policy.get("rule") or []


def _sensitive_buckets(plan):
    return [b for b in plan.resources("google_storage_bucket") if b.blocks("retention_policy")]


def _org_policies(p):
    out = {}
    for r in p.resources("google_org_policy_policy"):
        name = str(r.get("name") or "").rsplit("/", 1)[-1]
        rules = (r.get("spec.0") or {}).get("rules") or []
        out[name] = rules
    return out


# ------------------------------------------------------------------ lab
@requirement("R19.1", "A customer-managed key that rotates and can't be destroyed by accident",
             hint="google_kms_key_ring (location = region) + google_kms_crypto_key (ENCRYPT_DECRYPT, rotation_period <= 90 days, lifecycle { prevent_destroy = true })")
def key(plan):
    k = _key(plan)
    require(k.get("purpose", "ENCRYPT_DECRYPT") == "ENCRYPT_DECRYPT", f"purpose {k.get('purpose')}: storage needs ENCRYPT_DECRYPT")
    rot = _secs(k.get("rotation_period"))
    require(0 < rot <= 90 * 86400, f"rotation_period {k.get('rotation_period') or 'unset'}: rotate at least every 90 days")
    rings = plan.resources("google_kms_key_ring")
    require(rings and rings[0].get("location") == plan.variable_value("region"),
            "The key ring must be in the same location as the buckets that use it")
    protected = any((b.block("lifecycle") and (b.block("lifecycle").attr("prevent_destroy") or "").lower() == "true")
                    for b in plan.source.blocks("resource", "google_kms_crypto_key"))
    require(protected, "Add lifecycle { prevent_destroy = true } - destroying a key destroys all data encrypted with it")


@requirement("R19.2", "Only the Cloud Storage service agent can use the key, granted on the key",
             hint='google_kms_crypto_key_iam_member: roles/cloudkms.cryptoKeyEncrypterDecrypter for "serviceAccount:service-<project number>@gs-project-accounts.iam.gserviceaccount.com"')
def key_access(plan):
    k = _key(plan)
    grants = iam.grants(plan)
    on_key = [g for g in grants if g.scope == "kms_key" and g.target is not None and g.target.address == k.address]
    users = [g for g in on_key if g.role == "roles/cloudkms.cryptoKeyEncrypterDecrypter"]
    require(any(STORAGE_AGENT.match(g.principal) for g in users),
            "The Cloud Storage service agent can't use the key - every write to a CMEK bucket would fail")
    others = [g.principal for g in users if not STORAGE_AGENT.match(g.principal)]
    require(not others, f"Other principals can use the key: {others}")
    project = [f"{g.principal} {g.role}" for g in grants if g.scope == "project" and g.role.startswith("roles/cloudkms.")]
    require(not project, f"Project-level KMS roles reach every key: {project}")


@requirement("R19.3", "Backups and audit logs are encrypted with the customer-managed key",
             hint="encryption { default_kms_key_name = module.kms.storage_key_id } on the retention-protected buckets")
def cmek_buckets(plan):
    k = _key(plan)
    buckets = _sensitive_buckets(plan)
    require(len(buckets) >= 2, "Expected the backups and audit buckets")
    for b in buckets:
        enc = b.get("encryption.0") or {}
        require(enc or b.is_unknown("encryption"), f"{b.get('name')} uses Google-managed keys")
        ok = enc.get("default_kms_key_name") == k.get("id") or b.is_unknown("encryption.0.default_kms_key_name") \
            or plan.linked(b, "google_kms_crypto_key", "encryption.default_kms_key_name")
        require(ok, f"{b.get('name')} is not encrypted with the storage key")


@requirement("R19.4", "Cloud Armor blocks SQL injection and XSS",
             hint="rules with evaluatePreconfiguredWaf('sqli-v33-stable') and ('xss-v33-stable'), action deny(403)")
def waf(plan):
    rules = _rules(_policy(plan))
    def blocking(name):
        return [r for r in rules if name in str(((r.get("match") or [{}])[0].get("expr") or [{}])[0].get("expression", ""))
                and str(r.get("action", "")).startswith("deny")]
    require(blocking("sqli"), "No deny rule for the preconfigured SQL injection signatures")
    require(blocking("xss"), "No deny rule for the preconfigured XSS signatures")
    for r in rules:
        require(r.get("preview") is not True, f"Rule {r.get('priority')} is in preview mode - it logs but doesn't block")


@requirement("R19.5", "Each client is rate-limited",
             hint='a "throttle" (or rate_based_ban) rule with rate_limit_options { enforce_on_key = "IP"  exceed_action = "deny(429)" }')
def rate_limit(plan):
    rules = [r for r in _rules(_policy(plan)) if r.get("action") in ("throttle", "rate_based_ban")]
    require(rules, "No rate-limiting rule")
    opts = (rules[0].get("rate_limit_options") or [{}])[0]
    require(opts.get("enforce_on_key", "ALL") != "ALL", "Rate limit per client (enforce_on_key = \"IP\"), not globally")
    require(str(opts.get("exceed_action", "")).startswith("deny"), "Requests over the limit should be denied (429)")
    t = (opts.get("rate_limit_threshold") or [{}])[0]
    require(int(t.get("count") or 0) > 0 and int(t.get("interval_sec") or 0) > 0, "Set a rate_limit_threshold")
    default = [r for r in _rules(_policy(plan)) if int(r.get("priority") or 0) == 2147483647]
    require(default, "Keep an explicit default rule (priority 2147483647)")


@requirement("R19.6", "Every load balancer backend is behind the policy",
             hint="security_policy = module.armor.policy_id on the web and api backend services")
def attached(plan):
    pol = _policy(plan)
    backends = plan.resources("google_compute_backend_service")
    require(len(backends) >= 2, "Expected the web and api backend services")
    for b in backends:
        ok = b.get("security_policy") or b.is_unknown("security_policy") or plan.linked(b, "google_compute_security_policy", "security_policy")
        require(ok, f"{b.get('name')} has no Cloud Armor policy - attackers would just target that path")


@requirement("R19.7", "Organization policy guardrails are enforced on the project",
             hint="google_org_policy_policy for compute.vmExternalIpAccess (deny_all), storage.uniformBucketLevelAccess, sql.restrictPublicIp, iam.disableServiceAccountKeyCreation")
def guardrails(plan):
    pols = _org_policies(plan)
    for name, mode in GUARDRAILS.items():
        require(name in pols, f"No organization policy for {name}")
        rules = pols[name]
        if mode == "deny_all":
            require(any(str(r.get("deny_all", "")).upper() == "TRUE" for r in rules), f"{name} must deny_all")
        else:
            require(any(str(r.get("enforce", "")).upper() == "TRUE" for r in rules), f"{name} must be enforced")


@requirement("R19.8", "The deployed platform already complies with the guardrails",
             hint="Before enforcing a constraint, make sure nothing violates it - or the next change to that resource fails.")
def complies(plan):
    for r in plan.resources("google_compute_instance") + plan.resources("google_compute_instance_template"):
        nic = (r.blocks("network_interface") or [{}])[0]
        require(not nic.get("access_config"), f"{r.address} has an external IP but compute.vmExternalIpAccess denies them")
    for b in plan.resources("google_storage_bucket"):
        require(b.get("uniform_bucket_level_access") is True, f"Bucket {b.get('name')} doesn't use uniform access")
    for s in plan.resources("google_sql_database_instance"):
        require((s.get("settings.0.ip_configuration.0") or {}).get("ipv4_enabled") is False, f"{s.address} has a public IP")
    require(not plan.resources("google_service_account_key"), "A service account key exists")


@requirement("R19.9", "Deployed dev changes safely: nothing destroyed or replaced",
             hint="CMEK on an existing bucket and a security policy on a backend are in-place updates.")
def safe(plan):
    bad = [f"{r.address} would be {'REPLACED' if r.is_replaced else 'DESTROYED'}" +
           (f" (forced by: {', '.join('.'.join(map(str, p)) for p in r.replace_paths)})" if r.is_replaced else "")
           for r in plan.all_changes() if r.is_replaced or r.actions == ["delete"]]
    require(not bad, "Against the deployed dev environment:\n  " + "\n  ".join(bad))


@requirement("R19.10", "prod gets the same protections",
             hint="Same modules in prod: KMS, Cloud Armor, guardrails.")
def prod(plan):
    prod = plan.others["prod"]
    srcs = lambda p: {n: c.get("source") for n, c in p.configuration.get("root_module", {}).get("module_calls", {}).items()}
    require(srcs(plan) == srcs(prod), "dev and prod call different modules")
    require(set(GUARDRAILS) <= set(_org_policies(prod)), "prod is missing guardrails")
    require(prod.resources("google_compute_security_policy"), "prod has no Cloud Armor policy")


# ------------------------------------------------------------------ challenge
@requirement("C19.1", "Only images from Meridian's registry can run (Binary Authorization policy)",
             hint="google_binary_authorization_policy: default ALWAYS_DENY + ENFORCED_BLOCK_AND_AUDIT_LOG, admission_whitelist_patterns for the registry",
             level="challenge")
def binauthz(plan):
    p = plan.resources("google_binary_authorization_policy")
    require(p, "No Binary Authorization policy")
    rule = (p[0].get("default_admission_rule") or [{}])[0]
    require(rule.get("evaluation_mode") in ("ALWAYS_DENY", "REQUIRE_ATTESTATION"), "The default rule must deny (or require attestation)")
    require(rule.get("enforcement_mode") == "ENFORCED_BLOCK_AND_AUDIT_LOG", "Enforce the policy (not dry-run)")
    require(p[0].blocks("admission_whitelist_patterns") or p[0].is_unknown("admission_whitelist_patterns"),
            "Allow Meridian's own registry")


@requirement("C19.2", "Adaptive Protection watches for layer-7 DDoS",
             hint="adaptive_protection_config { layer_7_ddos_defense_config { enable = true } }", level="challenge")
def adaptive(plan):
    cfg = (_policy(plan).get("adaptive_protection_config.0.layer_7_ddos_defense_config.0") or {})
    require(cfg.get("enable") is True, "Adaptive Protection is off")


@requirement("C19.3", "A VPC Service Controls perimeter (dry run) around the data services",
             hint="google_access_context_manager_service_perimeter with use_explicit_dry_run_spec and restricted storage/sqladmin/secretmanager",
             level="challenge")
def perimeter(plan):
    p = plan.resources("google_access_context_manager_service_perimeter")
    require(p, "No service perimeter")
    require(p[0].get("use_explicit_dry_run_spec") is True, "Start the perimeter in dry-run mode")
    services = set((p[0].get("spec.0") or {}).get("restricted_services") or [])
    missing = {"storage.googleapis.com", "sqladmin.googleapis.com", "secretmanager.googleapis.com"} - services
    require(not missing, f"The perimeter doesn't restrict {sorted(missing)}")


@requirement("C19.4", "The KMS module refuses slow rotation",
             hint="validation rotation_days 1-90; tests/challenge/modules/kms must pass", level="challenge",
             test="kms_module.tftest.hcl")
def rotation_validation(plan):
    mods = plan.configuration.get("root_module", {}).get("module_calls", {})
    require(any("rotation_days" in m.get("module", {}).get("variables", {}) for m in mods.values()), "No module declares rotation_days")
