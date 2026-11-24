"""Unit tests for coursekit.iam (hand-built plan JSON)."""

import unittest

from coursekit import iam
from coursekit.plan import Plan

from .test_firewall import _ref, _res


def build(*items):
    items = [
        _res("google_service_account.ci", "google_service_account", {"account_id": "ci", "email": "ci@p.iam.gserviceaccount.com",
                                                                    "name": "projects/p/serviceAccounts/ci@p.iam.gserviceaccount.com"}),
        _res("google_project_iam_custom_role.r", "google_project_iam_custom_role", {"role_id": "deployer", "permissions": ["a.b.get", "a.b.update"]}),
        *items,
    ]
    return Plan({"resource_changes": [r for r, _ in items], "configuration": {"root_module": {"resources": [c for _, c in items]}}})


class Grants(unittest.TestCase):
    def test_member_resolved_by_email(self):
        plan = build(_res("google_project_iam_member.m", "google_project_iam_member",
                          {"role": "roles/logging.logWriter", "member": "serviceAccount:ci@p.iam.gserviceaccount.com"}))
        [g] = iam.grants(plan)
        self.assertEqual(g.principal, "sa:google_service_account.ci")
        self.assertEqual(g.scope, "project")

    def test_member_resolved_by_reference_when_unknown(self):
        plan = build(_res("google_project_iam_member.m", "google_project_iam_member", {"role": "roles/x"},
                          {"member": _ref("google_service_account.ci.email")}))
        [g] = iam.grants(plan)
        self.assertEqual(g.principal, "sa:google_service_account.ci")

    def test_binding_expands_members(self):
        plan = build(_res("google_project_iam_binding.b", "google_project_iam_binding",
                          {"role": "roles/editor", "members": ["user:a@x.com", "group:g@x.com"]}))
        gs = iam.grants(plan)
        self.assertEqual(sorted(g.principal for g in gs), ["group:g@x.com", "user:a@x.com"])
        self.assertTrue(all(g.is_basic for g in gs))

    def test_custom_role_permissions(self):
        plan = build(_res("google_project_iam_member.m", "google_project_iam_member", {"member": "serviceAccount:ci@p.iam.gserviceaccount.com"},
                          {"role": _ref("google_project_iam_custom_role.r.id")}))
        [g] = iam.grants(plan)
        self.assertEqual(iam.custom_role_permissions(plan, g), ["a.b.get", "a.b.update"])

    def test_service_account_level_target(self):
        plan = build(_res("google_service_account_iam_member.i", "google_service_account_iam_member",
                          {"role": "roles/iam.serviceAccountTokenCreator", "member": "group:plat@x.com"},
                          {"service_account_id": _ref("google_service_account.ci.name")}))
        [g] = iam.grants(plan)
        self.assertEqual(g.scope, "service_account")
        self.assertEqual(g.target.address, "google_service_account.ci")


if __name__ == "__main__":
    unittest.main()
