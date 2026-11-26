"""Effective IAM from a plan: who gets which role, where.

Collects grants from project-, service-account- and bucket-level IAM
resources (member, binding and policy styles), resolves principals that are
service accounts to their resources (by email value or by reference, so it
works before anything exists), and expands custom roles to permissions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .plan import Plan, Resource

BASIC_ROLES = {"roles/owner", "roles/editor", "roles/viewer"}

PROJECT_TYPES = ("google_project_iam_member", "google_project_iam_binding", "google_project_iam_policy")
SA_TYPES = ("google_service_account_iam_member", "google_service_account_iam_binding")
BUCKET_TYPES = ("google_storage_bucket_iam_member", "google_storage_bucket_iam_binding")
SECRET_TYPES = ("google_secret_manager_secret_iam_member", "google_secret_manager_secret_iam_binding")
REPO_TYPES = ("google_artifact_registry_repository_iam_member", "google_artifact_registry_repository_iam_binding")
RUN_TYPES = ("google_cloud_run_v2_service_iam_member", "google_cloud_run_v2_service_iam_binding",
             "google_cloud_run_service_iam_member", "google_cloud_run_service_iam_binding")
TOPIC_TYPES = ("google_pubsub_topic_iam_member", "google_pubsub_topic_iam_binding")
SUBSCRIPTION_TYPES = ("google_pubsub_subscription_iam_member", "google_pubsub_subscription_iam_binding")
KMS_TYPES = ("google_kms_crypto_key_iam_member", "google_kms_crypto_key_iam_binding")
PUBLIC_PRINCIPALS = {"allUsers", "allAuthenticatedUsers"}


@dataclass
class Grant:
    scope: str                 # project | service_account | bucket | secret | repository | run | topic | subscription
    role: str                  # role string, or "custom:<address>" when only known by reference
    principal: str             # "sa:<address>" for resolvable service accounts, else the member string
    source: Resource           # the IAM resource that creates the grant
    target: Resource | None = None   # SA or bucket resource for resource-level grants
    target_name: str | None = None   # bucket name / SA id when known as a value
    condition: dict | None = None

    @property
    def is_basic(self) -> bool:
        return self.role in BASIC_ROLES

    @property
    def kind(self) -> str:
        return self.principal.split(":", 1)[0]

    @property
    def is_public(self) -> bool:
        return self.principal in PUBLIC_PRINCIPALS


def _sa_by_email(plan: Plan, email: str) -> Resource | None:
    for sa in plan.resources("google_service_account"):
        if sa.get("email") == email:
            return sa
    return None


def _principal(plan: Plan, res: Resource, member: str | None, path: str) -> list[str]:
    """Principal keys for one member value (or the references behind it)."""
    if isinstance(member, str) and member:
        if member.startswith("serviceAccount:"):
            sa = _sa_by_email(plan, member.split(":", 1)[1])
            if sa is not None:
                return [f"sa:{sa.address}"]
        return [member]
    sas = plan.linked(res, "google_service_account", path)
    if sas:
        return [f"sa:{sa.address}" for sa in sas]
    pools = plan.linked(res, "google_iam_workload_identity_pool", path)
    if pools:
        return [f"principalSet:{pools[0].address}"]
    return ["unknown:" + ",".join(res.references(path)) if res.references(path) else "unknown:"]


def _role(plan: Plan, res: Resource) -> str:
    role = res.get("role")
    if isinstance(role, str) and role:
        return role
    custom = plan.linked(res, "google_project_iam_custom_role", "role")
    return f"custom:{custom[0].address}" if custom else "unknown"


def grants(plan: Plan) -> list[Grant]:
    out: list[Grant] = []
    for t in PROJECT_TYPES + SA_TYPES + BUCKET_TYPES + SECRET_TYPES + REPO_TYPES + RUN_TYPES + TOPIC_TYPES + SUBSCRIPTION_TYPES + KMS_TYPES:
        for r in plan.resources(t):
            scope = ("project" if t in PROJECT_TYPES else "service_account" if t in SA_TYPES
                     else "bucket" if t in BUCKET_TYPES else "secret" if t in SECRET_TYPES
                     else "repository" if t in REPO_TYPES else "run" if t in RUN_TYPES
                     else "topic" if t in TOPIC_TYPES else "subscription" if t in SUBSCRIPTION_TYPES else "kms_key")
            target, target_name = None, None
            if scope == "service_account":
                sas = plan.linked(r, "google_service_account", "service_account_id")
                target = sas[0] if sas else None
                target_name = r.get("service_account_id")
                if target is None and isinstance(target_name, str):
                    target = next((s for s in plan.resources("google_service_account") if s.get("name") == target_name), None)
            elif scope == "bucket":
                bks = plan.linked(r, "google_storage_bucket", "bucket")
                target = bks[0] if bks else None
                target_name = r.get("bucket")
                if target is None and isinstance(target_name, str):
                    target = next((b for b in plan.resources("google_storage_bucket") if b.get("name") == target_name), None)
            elif scope == "secret":
                secs = plan.linked(r, "google_secret_manager_secret", "secret_id")
                target = secs[0] if secs else None
                target_name = r.get("secret_id")
            elif scope == "repository":
                repos = plan.linked(r, "google_artifact_registry_repository", "repository")
                target = repos[0] if repos else None
                target_name = r.get("repository")
            elif scope == "topic":
                tops = plan.linked(r, "google_pubsub_topic", "topic")
                target = tops[0] if tops else None
                target_name = r.get("topic")
            elif scope == "subscription":
                subs = plan.linked(r, "google_pubsub_subscription", "subscription")
                target = subs[0] if subs else None
                target_name = r.get("subscription")
            elif scope == "kms_key":
                keys = plan.linked(r, "google_kms_crypto_key", "crypto_key_id")
                target = keys[0] if keys else None
                target_name = r.get("crypto_key_id")
            elif scope == "run":
                svcs = plan.linked(r, "google_cloud_run_v2_service", "name") or plan.linked(r, "google_cloud_run_service", "service")
                target = svcs[0] if svcs else None
                target_name = r.get("name") or r.get("service")
            cond = (r.get("condition") or [None])[0] if isinstance(r.get("condition"), list) else None
            if t.endswith("_policy"):
                try:
                    policy = json.loads(r.get("policy_data") or "{}")
                except json.JSONDecodeError:
                    policy = {}
                for b in policy.get("bindings", []):
                    for m in b.get("members", []):
                        out.append(Grant(scope, b.get("role", "unknown"), m, r))
                continue
            role = _role(plan, r)
            if t.endswith("_binding"):
                members = r.get("members") or []
                keys = [k for m in members for k in _principal(plan, r, m, "members")] or _principal(plan, r, None, "members")
            else:
                keys = _principal(plan, r, r.get("member"), "member")
            for k in keys:
                out.append(Grant(scope, role, k, r, target, target_name if isinstance(target_name, str) else None, cond))
    return out


def custom_role_permissions(plan: Plan, grant: Grant) -> list[str] | None:
    """Permissions of a custom role grant (None for predefined roles)."""
    role_res = None
    if grant.role.startswith("custom:"):
        role_res = plan.resource(grant.role.split(":", 1)[1])
    elif "/roles/" in grant.role and not grant.role.startswith("roles/"):
        role_res = next((c for c in plan.resources("google_project_iam_custom_role")
                         if grant.role.endswith("/roles/" + str(c.get("role_id")))), None)
    if role_res is None:
        return None
    return list(role_res.get("permissions") or [])


# Lesson 16's Terraform apply identity. It creates service accounts, keys and IAM grants, so it
# needs project-wide admin roles that would be findings for anyone else. What protects it is that
# only workflows on main can use it, behind an environment with reviewers.
DEPLOYER_ACCOUNT_ID = "meridian-ci-apply"


def is_deployer(plan: Plan, grant: Grant) -> bool:
    """True for grants to the Terraform apply identity (meridian-ci-apply)."""
    if grant.principal.startswith("sa:"):
        sa = plan.resource(grant.principal[3:])
        return sa is not None and sa.get("account_id") == DEPLOYER_ACCOUNT_ID
    return grant.principal.startswith(f"serviceAccount:{DEPLOYER_ACCOUNT_ID}@")


def for_principal(all_grants: list[Grant], principal: str, scope: str | None = None) -> list[Grant]:
    return [g for g in all_grants if g.principal == principal and (scope is None or g.scope == scope)]
