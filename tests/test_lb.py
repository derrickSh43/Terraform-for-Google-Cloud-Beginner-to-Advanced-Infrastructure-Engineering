"""Unit tests for coursekit.lb (hand-built plan JSON, no Terraform needed)."""

import unittest

from coursekit import lb
from coursekit.plan import Plan

from .test_firewall import _ref, _res

VM_LINK = "https://www.googleapis.com/compute/v1/projects/p/zones/z/instances/web-1"


def chain(port_name="http", named_port="http", redirect=False, with_hc=True):
    items = [
        _res("google_compute_instance.web", "google_compute_instance", {"self_link": VM_LINK, "tags": ["web"]}),
        _res("google_compute_health_check.hc", "google_compute_health_check", {"http_health_check": [{"port": 80}]}),
        _res("google_compute_instance_group.ig", "google_compute_instance_group",
             {"instances": [VM_LINK], "named_port": [{"name": named_port, "port": 80}]}),
        _res("google_compute_backend_service.be", "google_compute_backend_service",
             {"port_name": port_name, "backend": [{}]},
             {"backend": [{"group": _ref("google_compute_instance_group.ig.id")}],
              **({"health_checks": _ref("google_compute_health_check.hc.id")} if with_hc else {})}),
        _res("google_compute_url_map.um", "google_compute_url_map",
             {"default_url_redirect": [{"https_redirect": True}]} if redirect else {},
             {} if redirect else {"default_service": _ref("google_compute_backend_service.be.id")}),
        _res("google_compute_target_http_proxy.px", "google_compute_target_http_proxy", {},
             {"url_map": _ref("google_compute_url_map.um.id")}),
        _res("google_compute_global_forwarding_rule.fr", "google_compute_global_forwarding_rule", {"port_range": "80"},
             {"target": _ref("google_compute_target_http_proxy.px.id")}),
    ]
    return Plan({"resource_changes": [r for r, _ in items], "configuration": {"root_module": {"resources": [c for _, c in items]}}})


class Trace(unittest.TestCase):
    def test_full_chain(self):
        plan = chain()
        [f] = lb.trace(plan)
        self.assertEqual(f.problems, [])
        self.assertEqual(f.backends[0].port, 80)
        self.assertTrue(f.serves(plan.resource("google_compute_instance.web")))

    def test_named_port_mismatch_is_reported(self):
        [f] = lb.trace(chain(port_name="web"))
        self.assertIsNone(f.backends[0].port)
        self.assertTrue(any("named_port" in p for p in f.problems))

    def test_missing_health_check_is_reported(self):
        [f] = lb.trace(chain(with_hc=False))
        self.assertTrue(any("no health check" in p for p in f.problems))

    def test_redirect_frontend_has_no_backends(self):
        [f] = lb.trace(chain(redirect=True))
        self.assertTrue(f.redirects_to_https)
        self.assertEqual(f.backends, [])

    def test_port_range(self):
        self.assertTrue(lb.port_in_range(80, "80"))
        self.assertTrue(lb.port_in_range(443, "443-443"))
        self.assertFalse(lb.port_in_range(80, "443"))


if __name__ == "__main__":
    unittest.main()
