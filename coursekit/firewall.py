"""Offline VPC firewall evaluator.

Answers "would this flow be allowed?" from a Terraform plan, standing in for
real connectivity tests. It models the parts of Google Cloud VPC firewall
semantics the course relies on:

  * rules apply per VPC network, per direction (INGRESS default / EGRESS);
  * lowest priority number wins; at equal priority DENY beats ALLOW;
  * implied rules: deny all ingress, allow all egress (priority 65535);
  * targets: target_tags, target_service_accounts, or every instance;
  * ingress sources: source_ranges, source_tags, source_service_accounts
    (no source at all means 0.0.0.0/0); egress uses destination_ranges;
  * internet traffic needs an external IP on the target (access_config);
    IAP TCP forwarding (35.235.240.0/20) reaches internal IPs.

  * internet egress needs an external IP, or a Cloud NAT on a router in the
    VM's network and region that covers its subnet (ALL_SUBNETWORKS_* or
    LIST_OF_SUBNETWORKS); Google API VIPs work via Private Google Access;
  * internal sources (e.g. a peered VPC) are given as IPs with internal_ip().

Limitations (documented for students): no hierarchical/network firewall
policies, no custom routes, peering is asserted by checks rather than routed
here, and instance IPs are approximated by their subnet range.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field

from .plan import Plan, Resource

INTERNET_IP = "203.0.113.10"      # TEST-NET-3, stands in for "anyone on the internet"
IAP_IP = "35.235.240.10"          # inside Google's IAP TCP forwarding range
IAP_RANGE = "35.235.240.0/20"
INTERNAL_RANGES = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10")
GOOGLE_API_VIPS = ("199.36.153.8/30", "199.36.153.4/30")   # private / restricted.googleapis.com


@dataclass
class Endpoint:
    label: str
    kind: str                       # "internet" | "iap" | "ip" | "internal" | "instance"
    ip: str | None = None
    instance: Resource | None = None
    tags: set[str] = field(default_factory=set)
    sa_keys: set[str] = field(default_factory=set)
    network: str | None = None
    cidr: str | None = None
    external_ip: bool = False
    subnet: Resource | None = None


@dataclass
class Verdict:
    allowed: bool
    reason: str

    def __bool__(self) -> bool:
        return self.allowed


def _net(s: str):
    return ipaddress.ip_network(s, strict=False)


def _overlaps(range_: str, cidr_or_ip: str) -> bool:
    try:
        return _net(range_).overlaps(_net(cidr_or_ip))
    except ValueError:
        return False


class Firewall:
    def __init__(self, plan: Plan):
        self.plan = plan
        self.rules = plan.resources("google_compute_firewall")

    # ---- identity helpers ---------------------------------------------
    def _network_key_of(self, res: Resource, path: str) -> str | None:
        val = res.get(path)
        if isinstance(val, str) and val:
            target = self.plan.find_by_id(val)      # known IDs, e.g. from a deployed state
            if target is not None and target.type == "google_compute_network":
                return target.address
            if target is not None and target.type == "google_compute_subnetwork":
                return self._network_key_of(target, "network")
            return val.rsplit("/", 1)[-1]           # "default" or a self_link
        nets = self.plan.linked(res, "google_compute_network", path)
        if nets:
            return nets[0].address
        subnets = self.plan.linked(res, "google_compute_subnetwork", path)
        if subnets:
            return self._network_key_of(subnets[0], "network")
        return None

    def _sa_keys(self, res: Resource, path: str) -> set[str]:
        keys: set[str] = set()
        val = res.get(path)
        if isinstance(val, str):
            keys.add(val)
        elif isinstance(val, list):
            keys.update(v for v in val if isinstance(v, str))
        keys.update(sa.address for sa in self.plan.linked(res, "google_service_account", path))
        return keys

    def instance(self, inst: Resource, label: str | None = None) -> Endpoint:
        # Resolve via the subnetwork (value or configuration reference). If that fails
        # because the subnet ID is only known after apply (e.g. passed in through a
        # module variable), the network is unknown: None matches any rule's network.
        nic_net = self._network_key_of(inst, "network_interface.0.subnetwork")
        if nic_net is None and not inst.is_unknown("network_interface.0.subnetwork"):
            nic_net = self._network_key_of(inst, "network_interface.0.network")
        cidr = None
        subnets = self.plan.linked(inst, "google_compute_subnetwork", "network_interface.subnetwork")
        if not subnets:
            found = self.plan.find_by_id(inst.get("network_interface.0.subnetwork"))
            subnets = [found] if found is not None else []
        if subnets:
            cidr = subnets[0].get("ip_cidr_range")
        nic = (inst.blocks("network_interface") or [{}])[0]
        external = bool(nic.get("access_config")) or inst.is_unknown("network_interface.0.access_config")
        return Endpoint(
            label=label or inst.address,
            kind="instance",
            instance=inst,
            tags=set(inst.get("tags") or []),
            sa_keys=self._sa_keys(inst, "service_account.0.email") if inst.blocks("service_account") else set(),
            network=nic_net,  # None = unresolvable (e.g. subnet ID only known after apply)
            cidr=cidr,
            external_ip=external,
            subnet=subnets[0] if subnets else None,
        )

    @staticmethod
    def internet() -> Endpoint:
        return Endpoint("internet", "internet", ip=INTERNET_IP)

    @staticmethod
    def iap() -> Endpoint:
        return Endpoint("IAP", "iap", ip=IAP_IP)

    @staticmethod
    def ip(addr: str) -> Endpoint:
        return Endpoint(addr, "ip", ip=addr)

    @staticmethod
    def internal_ip(addr: str, label: str | None = None) -> Endpoint:
        """A private address reaching VMs over internal routing (peered VPC, VPN)."""
        return Endpoint(label or addr, "internal", ip=addr)

    # ---- internet egress -------------------------------------------------
    def nat_for(self, src: Endpoint) -> Verdict:
        """Is there a Cloud NAT that translates this VM's traffic?"""
        region = src.subnet.get("region") if src.subnet is not None else None
        subnet_name = src.subnet.get("name") if src.subnet is not None else "its subnet"
        for nat in self.plan.resources("google_compute_router_nat"):
            if region and nat.get("region") and nat.get("region") != region:
                continue
            routers = self.plan.linked(nat, "google_compute_router", "router")
            if not routers and isinstance(nat.get("router"), str):
                routers = [r for r in self.plan.resources("google_compute_router")
                           if r.get("name") == nat.get("router") and (not region or r.get("region") == region)]
            if routers and src.network is not None:
                net = self._network_key_of(routers[0], "network")
                if net is not None and net != src.network:
                    continue
            mode = nat.get("source_subnetwork_ip_ranges_to_nat", "")
            if mode.startswith("ALL_SUBNETWORKS"):
                return Verdict(True, f"{nat.address} ({mode})")
            if mode == "LIST_OF_SUBNETWORKS":
                entries = nat.blocks("subnetwork")
                if src.subnet is not None:
                    ids = {src.subnet.get("id"), src.subnet.get("self_link"), src.subnet.get("name")} - {None}
                    if any(e.get("name") in ids for e in entries):
                        return Verdict(True, f"{nat.address} (lists {subnet_name})")
                if any(e.get("name") is None for e in entries) or nat.is_unknown("subnetwork"):
                    return Verdict(True, f"{nat.address} (subnet list known only after apply; assumed to cover)")
        return Verdict(False, f"{src.label} has no external IP and no Cloud NAT covers {subnet_name}")

    # ---- rule matching -------------------------------------------------
    def _rule_network(self, rule: Resource) -> str:
        return self._network_key_of(rule, "network") or "default"

    def _targets(self, rule: Resource, ep: Endpoint) -> bool:
        tags = set(rule.get("target_tags") or [])
        sas = self._sa_keys(rule, "target_service_accounts")
        if not tags and not sas:
            return True
        return bool(tags & ep.tags) or bool(sas & ep.sa_keys)

    @staticmethod
    def _proto_match(blocks: list[dict], protocol: str, port: int | None) -> bool:
        for b in blocks:
            proto = str(b.get("protocol", "")).lower()
            if proto not in ("all", protocol, {"tcp": "6", "udp": "17", "icmp": "1"}.get(protocol, "?")):
                continue
            ports = b.get("ports") or []
            if not ports or port is None:
                return True
            for p in ports:
                p = str(p)
                if "-" in p:
                    lo, hi = p.split("-", 1)
                    if int(lo) <= port <= int(hi):
                        return True
                elif int(p) == port:
                    return True
        return False

    def _ingress_source(self, rule: Resource, src: Endpoint) -> bool:
        ranges = rule.get("source_ranges") or []
        stags = set(rule.get("source_tags") or [])
        ssas = self._sa_keys(rule, "source_service_accounts")
        if not ranges and not stags and not ssas:
            ranges = ["0.0.0.0/0"]
        if src.kind == "instance":
            if stags & src.tags or ssas & src.sa_keys:
                return True
            return any(src.cidr and _overlaps(r, src.cidr) for r in ranges)
        return any(_overlaps(r, src.ip or "") for r in ranges)

    def _egress_dest(self, rule: Resource, dst: Endpoint) -> bool:
        ranges = rule.get("destination_ranges") or ["0.0.0.0/0"]
        target = dst.cidr if dst.kind == "instance" else dst.ip
        return any(target and _overlaps(r, target) for r in ranges)

    def _decide(self, candidates: list[Resource], default_allow: bool, direction: str) -> Verdict:
        if not candidates:
            return Verdict(default_allow, f"implied {direction.lower()} {'allow' if default_allow else 'deny'} rule")

        def key(r: Resource):
            return (int(r.get("priority", 1000)), 0 if r.blocks("deny") else 1)

        best = sorted(candidates, key=key)[0]
        allowed = not best.blocks("deny")
        return Verdict(allowed, f"{best.address} ({'allow' if allowed else 'deny'}, priority {best.get('priority', 1000)})")

    def _matching(self, direction: str, network: str, target: Endpoint, peer: Endpoint, protocol: str, port: int | None):
        out = []
        for rule in self.rules:
            if rule.get("disabled"):
                continue
            if str(rule.get("direction") or "INGRESS").upper() != direction:
                continue
            if network is not None and self._rule_network(rule) != network:
                continue
            if not self._targets(rule, target):
                continue
            blocks = rule.blocks("deny") or rule.blocks("allow")
            if not self._proto_match(blocks, protocol, port):
                continue
            if direction == "INGRESS" and not self._ingress_source(rule, peer):
                continue
            if direction == "EGRESS" and not self._egress_dest(rule, peer):
                continue
            out.append(rule)
        return out

    # ---- public API ----------------------------------------------------
    def evaluate(self, src: Endpoint, dst: Endpoint, protocol: str = "tcp", port: int | None = None) -> Verdict:
        protocol = protocol.lower()
        if src.kind == "instance":
            egress = self._decide(
                self._matching("EGRESS", src.network, src, dst, protocol, port), True, "EGRESS"
            )
            if not egress:
                return Verdict(False, f"egress blocked at source by {egress.reason}")

        if dst.kind != "instance":
            ip = dst.ip or ""
            internal = any(_overlaps(r, ip) for r in INTERNAL_RANGES)
            if src.kind == "instance" and not internal and not src.external_ip:
                if any(_overlaps(r, ip) for r in GOOGLE_API_VIPS):
                    pga = src.subnet is None or src.subnet.get("private_ip_google_access") is not False
                    return Verdict(pga, "Private Google Access" if pga else f"{src.label} subnet has Private Google Access off")
                nat = self.nat_for(src)
                return Verdict(nat.allowed, ("via Cloud NAT " + nat.reason) if nat.allowed else nat.reason)
            return Verdict(True, "destination is outside the VPC; only egress applies")

        if src.kind == "internet" or src.kind == "ip":
            if not dst.external_ip:
                return Verdict(False, f"{dst.label} has no external IP address")
        if src.kind == "instance" and None not in (src.network, dst.network) and src.network != dst.network:
            return Verdict(False, f"{src.label} and {dst.label} are on different VPC networks")

        ingress = self._decide(
            self._matching("INGRESS", dst.network, dst, src, protocol, port), False, "INGRESS"
        )
        return Verdict(ingress.allowed, ingress.reason)

    def rules_open_to_world(self, port: int, protocol: str = "tcp") -> list[Resource]:
        """ALLOW ingress rules that accept `port` from 0.0.0.0/0."""
        out = []
        for rule in self.rules:
            if rule.get("disabled") or str(rule.get("direction") or "INGRESS").upper() != "INGRESS":
                continue
            if not rule.blocks("allow") or not self._proto_match(rule.blocks("allow"), protocol, port):
                continue
            ranges = rule.get("source_ranges") or []
            if not ranges and not rule.get("source_tags") and not rule.get("source_service_accounts"):
                ranges = ["0.0.0.0/0"]
            if any(r in ("0.0.0.0/0", "::/0") for r in ranges):
                out.append(rule)
        return out
