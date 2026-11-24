"""Unit tests for coursekit.firewall using hand-built plan JSON (no Terraform needed)."""

import unittest

from coursekit.firewall import Firewall
from coursekit.plan import Plan


def _res(address, rtype, after, expressions=None, unknown=None):
    name = address.split(".")[1].split("[")[0]
    return (
        {"address": address, "mode": "managed", "type": rtype, "name": name,
         "change": {"actions": ["create"], "after": after, "after_unknown": unknown or {}}},
        {"address": address.split("[")[0], "mode": "managed", "type": rtype, "name": name, "expressions": expressions or {}},
    )


def _ref(*refs):
    return {"references": list(refs)}


def build(rules, extra=()):
    items = [
        _res("google_compute_network.vpc", "google_compute_network", {"name": "vpc"}),
        _res("google_compute_subnetwork.web", "google_compute_subnetwork", {"ip_cidr_range": "10.0.1.0/24"},
             {"network": _ref("google_compute_network.vpc.id", "google_compute_network.vpc")}),
        _res("google_compute_subnetwork.app", "google_compute_subnetwork", {"ip_cidr_range": "10.0.2.0/24"},
             {"network": _ref("google_compute_network.vpc.id", "google_compute_network.vpc")}),
        _res("google_service_account.web", "google_service_account", {"account_id": "web"}),
        _res("google_service_account.app", "google_service_account", {"account_id": "app"}),
        _res("google_compute_instance.web", "google_compute_instance",
             {"tags": ["web"], "network_interface": [{"access_config": [{}]}], "service_account": [{"scopes": []}]},
             {"network_interface": [{"subnetwork": _ref("google_compute_subnetwork.web.id")}],
              "service_account": [{"email": _ref("google_service_account.web.email")}]}),
        _res("google_compute_instance.app", "google_compute_instance",
             {"tags": ["app"], "network_interface": [{}], "service_account": [{"scopes": []}]},
             {"network_interface": [{"subnetwork": _ref("google_compute_subnetwork.app.id")}],
              "service_account": [{"email": _ref("google_service_account.app.email")}]}),
    ]
    for i, (after, exprs) in enumerate(rules):
        exprs = {"network": _ref("google_compute_network.vpc.id"), **exprs}
        items.append(_res(f"google_compute_firewall.r{i}", "google_compute_firewall", after, exprs))
    items.extend(extra)
    data = {
        "resource_changes": [rc for rc, _ in items],
        "configuration": {"root_module": {"resources": [cfg for _, cfg in items]}},
    }
    plan = Plan(data)
    fw = Firewall(plan)
    web = fw.instance(plan.resource("google_compute_instance.web"), "web")
    app = fw.instance(plan.resource("google_compute_instance.app"), "app")
    return fw, web, app


def _subnet(fw, address, region, sid=None):
    """Give a test subnet a region (and optionally a known id) after build()."""
    s = fw.plan.resource(address)
    s.after["region"] = region
    if sid:
        s.after["id"] = sid
    return s


def allow(port, **kw):
    return {"direction": "INGRESS", "priority": kw.pop("priority", 1000),
            "allow": [{"protocol": "tcp", "ports": [str(port)]}], **kw}


def deny(port, **kw):
    return {"direction": "INGRESS", "priority": kw.pop("priority", 1000),
            "deny": [{"protocol": "tcp", "ports": [str(port)]}], **kw}


class ImpliedRules(unittest.TestCase):
    def test_ingress_denied_by_default(self):
        fw, web, _ = build([])
        v = fw.evaluate(fw.internet(), web, "tcp", 80)
        self.assertFalse(v)
        self.assertIn("implied", v.reason)

    def test_egress_allowed_by_default(self):
        fw, web, _ = build([])
        self.assertTrue(fw.evaluate(web, fw.ip("203.0.113.5"), "tcp", 443))


class Matching(unittest.TestCase):
    def test_target_tag_scopes_rule(self):
        fw, web, app = build([(allow(80, source_ranges=["0.0.0.0/0"], target_tags=["web"]), {})])
        self.assertTrue(fw.evaluate(fw.internet(), web, "tcp", 80))
        self.assertFalse(fw.evaluate(web, app, "tcp", 80))

    def test_port_range(self):
        fw, web, _ = build([({"direction": "INGRESS", "allow": [{"protocol": "tcp", "ports": ["8000-8100"]}],
                              "source_ranges": ["0.0.0.0/0"]}, {})])
        self.assertTrue(fw.evaluate(fw.internet(), web, "tcp", 8080))
        self.assertFalse(fw.evaluate(fw.internet(), web, "tcp", 9000))

    def test_protocol_all(self):
        fw, web, _ = build([({"direction": "INGRESS", "allow": [{"protocol": "all"}], "source_ranges": ["0.0.0.0/0"]}, {})])
        self.assertTrue(fw.evaluate(fw.internet(), web, "udp", 53))

    def test_source_tags_match_internal_only(self):
        fw, web, app = build([(allow(8080, source_tags=["web"], target_tags=["app"]), {})])
        self.assertTrue(fw.evaluate(web, app, "tcp", 8080))
        self.assertFalse(fw.evaluate(app, app, "tcp", 8080))

    def test_no_source_means_anywhere(self):
        fw, web, _ = build([(allow(80, target_tags=["web"]), {})])
        self.assertTrue(fw.evaluate(fw.internet(), web, "tcp", 80))

    def test_service_account_targets(self):
        rule = allow(8080)
        exprs = {"source_service_accounts": _ref("google_service_account.web.email"),
                 "target_service_accounts": _ref("google_service_account.app.email")}
        fw, web, app = build([(rule, exprs)])
        self.assertTrue(fw.evaluate(web, app, "tcp", 8080))
        self.assertFalse(fw.evaluate(app, app, "tcp", 8080))

    def test_disabled_rule_ignored(self):
        fw, web, _ = build([(allow(80, source_ranges=["0.0.0.0/0"], disabled=True), {})])
        self.assertFalse(fw.evaluate(fw.internet(), web, "tcp", 80))


class Priority(unittest.TestCase):
    def test_lower_number_wins(self):
        fw, web, _ = build([
            (allow(80, source_ranges=["0.0.0.0/0"], priority=1000), {}),
            (deny(80, source_ranges=["0.0.0.0/0"], priority=900), {}),
        ])
        v = fw.evaluate(fw.internet(), web, "tcp", 80)
        self.assertFalse(v)
        self.assertIn("r1", v.reason)

    def test_deny_wins_tie(self):
        fw, web, _ = build([
            (allow(80, source_ranges=["0.0.0.0/0"]), {}),
            (deny(80, source_ranges=["0.0.0.0/0"]), {}),
        ])
        self.assertFalse(fw.evaluate(fw.internet(), web, "tcp", 80))


class Reachability(unittest.TestCase):
    def test_no_external_ip_blocks_internet(self):
        fw, _, app = build([(allow(8080, source_ranges=["0.0.0.0/0"]), {})])
        v = fw.evaluate(fw.internet(), app, "tcp", 8080)
        self.assertFalse(v)
        self.assertIn("no external IP", v.reason)

    def test_iap_reaches_internal_vm(self):
        fw, _, app = build([(allow(22, source_ranges=["35.235.240.0/20"]), {})])
        self.assertTrue(fw.evaluate(fw.iap(), app, "tcp", 22))

    def test_egress_deny_blocks_before_ingress(self):
        egress_deny = {"direction": "EGRESS", "priority": 65000, "deny": [{"protocol": "all"}],
                       "destination_ranges": ["0.0.0.0/0"], "target_tags": ["web"]}
        fw, web, app = build([(egress_deny, {}), (allow(8080, source_tags=["web"]), {})])
        v = fw.evaluate(web, app, "tcp", 8080)
        self.assertFalse(v)
        self.assertIn("egress", v.reason)

    def test_unresolvable_network_matches_rules(self):
        # A VM inside a module gets its subnet through a variable whose value is
        # only known after apply: the network is unknown, not "default".
        fw, _, _ = build([(allow(22, source_ranges=["35.235.240.0/20"], target_tags=["db"]), {})])
        rc, cfg = _res("google_compute_instance.db", "google_compute_instance",
                       {"tags": ["db"], "network_interface": [{}]},
                       {"network_interface": [{"subnetwork": _ref("var.subnet_id")}]},
                       unknown={"network_interface": [{"subnetwork": True, "network": True}]})
        plan = Plan({"resource_changes": [rc], "configuration": {"root_module": {"resources": [cfg]}}})
        db = Firewall(plan).instance(plan.resource("google_compute_instance.db"), "db")
        self.assertIsNone(db.network)
        self.assertTrue(fw.evaluate(fw.iap(), db, "tcp", 22))

    def test_known_ids_resolve_through_subnet(self):
        # With deployed state, IDs are known strings; they must resolve to the same network.
        net = _res("google_compute_network.vpc", "google_compute_network", {"id": "net-1"})
        sub = _res("google_compute_subnetwork.s", "google_compute_subnetwork", {"id": "sub-1", "network": "net-1", "ip_cidr_range": "10.0.0.0/24"})
        vm = _res("module.x.google_compute_instance.vm", "google_compute_instance",
                  {"tags": ["web"], "network_interface": [{"subnetwork": "sub-1", "access_config": [{}]}]})
        vm[0]["module_address"] = "module.x"
        rule = _res("google_compute_firewall.r", "google_compute_firewall",
                    {"network": "net-1", "direction": "INGRESS", "priority": 1000, "source_ranges": ["0.0.0.0/0"],
                     "target_tags": ["web"], "allow": [{"protocol": "tcp", "ports": ["80"]}]})
        items = [net, sub, vm, rule]
        plan = Plan({"resource_changes": [r for r, _ in items], "configuration": {"root_module": {"resources": [c for _, c in items]}}})
        fw = Firewall(plan)
        ep = fw.instance(plan.resource("module.x.google_compute_instance.vm"), "vm")
        self.assertEqual(ep.network, "google_compute_network.vpc")
        self.assertEqual(ep.cidr, "10.0.0.0/24")
        self.assertTrue(fw.evaluate(fw.internet(), ep, "tcp", 80))

    def test_private_vm_needs_nat_for_internet(self):
        fw, web, app = build([])
        self.assertTrue(fw.evaluate(web, fw.ip("151.101.2.132"), "tcp", 443))      # external IP
        v = fw.evaluate(app, fw.ip("151.101.2.132"), "tcp", 443)
        self.assertFalse(v)
        self.assertIn("no Cloud NAT", v.reason)

    def test_nat_all_subnetworks(self):
        router = _res("google_compute_router.r", "google_compute_router", {"name": "r", "region": "us-central1"},
                      {"network": _ref("google_compute_network.vpc.id")})
        nat = _res("google_compute_router_nat.n", "google_compute_router_nat",
                   {"region": "us-central1", "source_subnetwork_ip_ranges_to_nat": "ALL_SUBNETWORKS_ALL_IP_RANGES"},
                   {"router": _ref("google_compute_router.r.name")})
        fw, _, app = build([], extra=[router, nat])
        app.subnet = _subnet(fw, "google_compute_subnetwork.app", "us-central1")
        self.assertTrue(fw.evaluate(app, fw.ip("151.101.2.132"), "tcp", 443))

    def test_nat_list_must_include_subnet(self):
        nat = _res("google_compute_router_nat.n", "google_compute_router_nat",
                   {"region": "us-central1", "source_subnetwork_ip_ranges_to_nat": "LIST_OF_SUBNETWORKS",
                    "subnetwork": [{"name": "sub-web"}]})
        fw, _, app = build([], extra=[nat])
        app.subnet = _subnet(fw, "google_compute_subnetwork.app", "us-central1", sid="sub-app")
        self.assertFalse(fw.evaluate(app, fw.ip("151.101.2.132"), "tcp", 443))

    def test_google_api_vip_uses_private_google_access(self):
        fw, _, app = build([])
        self.assertTrue(fw.evaluate(app, fw.ip("199.36.153.9"), "tcp", 443))

    def test_world_open_detection(self):
        fw, _, _ = build([(allow(22, source_ranges=["0.0.0.0/0"]), {}), (allow(80, source_ranges=["0.0.0.0/0"]), {})])
        self.assertEqual([r.address for r in fw.rules_open_to_world(22)], ["google_compute_firewall.r0"])


if __name__ == "__main__":
    unittest.main()
