"""Failure-domain analyser: what is left of each workload when a zone goes down?

Reads compute, database and container resources from a plan, works out which zones each one runs in
and how much capacity it has at minimum and maximum scale, then "removes" a zone and recomputes.

Rules (documented in docs/VALIDATION.md):
  * regional MIG     zones = distribution_policy_zones (or every zone of the region); capacity from the
                     autoscaler that targets it (min/max_replicas), else target_size. EVEN distribution
                     means a zone holds at most ceil(n / zones) instances - that's what one zone loss costs.
  * zonal MIG / VM   all capacity in one zone.
  * Cloud SQL        REGIONAL fails over to its standby (survives); ZONAL lives in one zone.
  * GKE cluster      a region location survives; a zone location doesn't.
  * Memorystore      STANDARD_HA survives; BASIC doesn't.
  * Cloud Run, Cloud Functions, Pub/Sub, buckets: regional or global services, survive a zone loss.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from .plan import Plan, Resource

REGION_ZONES = {
    "us-central1": ["us-central1-a", "us-central1-b", "us-central1-c", "us-central1-f"],
    "us-east1": ["us-east1-b", "us-east1-c", "us-east1-d"],
    "europe-west2": ["europe-west2-a", "europe-west2-b", "europe-west2-c"],
}
UNKNOWN_ZONE = "<one zone, chosen by Google>"


@dataclass
class Workload:
    address: str
    kind: str                      # "regional-mig" | "zonal-mig" | "vm" | "sql" | "gke" | "redis"
    zones: list[str]               # zones holding capacity; [] = regional service with automatic failover
    min_capacity: int
    max_capacity: int
    resource: Resource | None = field(default=None, repr=False)

    @property
    def failover(self) -> bool:
        return not self.zones

    def after_losing(self, zone: str, at: str = "min") -> int:
        n = self.min_capacity if at == "min" else self.max_capacity
        if self.failover:
            return n
        if zone not in self.zones and not (UNKNOWN_ZONE in self.zones):
            return n
        if len(self.zones) == 1 or UNKNOWN_ZONE in self.zones:
            return 0
        return n - math.ceil(n / len(self.zones))


def region_zones(region: str) -> list[str]:
    return REGION_ZONES.get(region, [f"{region}-a", f"{region}-b", f"{region}-c"])


def _region_of(r: Resource, plan: Plan) -> str:
    return r.get("region") or plan.variable_value("region") or "us-central1"


def _autoscaler_for(plan: Plan, mig: Resource) -> Resource | None:
    for a in plan.resources("google_compute_region_autoscaler") + plan.resources("google_compute_autoscaler"):
        if a.module == mig.module and (plan.linked(a, mig.type, "target") and mig in plan.linked(a, mig.type, "target")):
            return a
    return None


def _scale(plan: Plan, mig: Resource) -> tuple[int, int]:
    auto = _autoscaler_for(plan, mig)
    if auto is not None:
        pol = (auto.get("autoscaling_policy") or [{}])[0]
        return int(pol.get("min_replicas") or 0), int(pol.get("max_replicas") or 0)
    n = int(mig.get("target_size") or 0)
    return n, n


def workloads(plan: Plan) -> list[Workload]:
    out: list[Workload] = []
    for r in plan.resources("google_compute_region_instance_group_manager"):
        zones = list(r.get("distribution_policy_zones") or []) or region_zones(_region_of(r, plan))
        lo, hi = _scale(plan, r)
        out.append(Workload(r.address, "regional-mig", zones, lo, hi, r))
    for r in plan.resources("google_compute_instance_group_manager"):
        lo, hi = _scale(plan, r)
        out.append(Workload(r.address, "zonal-mig", [r.get("zone") or UNKNOWN_ZONE], lo, hi, r))
    for r in plan.resources("google_compute_instance"):
        out.append(Workload(r.address, "vm", [r.get("zone") or UNKNOWN_ZONE], 1, 1, r))
    for r in plan.resources("google_sql_database_instance"):
        s = (r.get("settings") or [{}])[0]
        if s.get("availability_type") == "REGIONAL":
            out.append(Workload(r.address, "sql", [], 1, 1, r))
        else:
            pref = (s.get("location_preference") or [{}])[0].get("zone")
            out.append(Workload(r.address, "sql", [pref or UNKNOWN_ZONE], 1, 1, r))
    for r in plan.resources("google_container_cluster"):
        loc = str(r.get("location") or "")
        zonal = bool(re.search(r"-[a-z]$", loc))
        out.append(Workload(r.address, "gke", [loc] if zonal else [], 1, 1, r))
    for r in plan.resources("google_redis_instance"):
        ha = r.get("tier") == "STANDARD_HA"
        out.append(Workload(r.address, "redis", [] if ha else [r.get("location_id") or UNKNOWN_ZONE], 1, 1, r))
    return out


def zones_in_play(plan: Plan) -> list[str]:
    zs = set(region_zones(plan.variable_value("region") or "us-central1"))
    for w in workloads(plan):
        zs |= {z for z in w.zones if z != UNKNOWN_ZONE}
    return sorted(zs)


def lose_zone(plan: Plan, zone: str, at: str = "min") -> dict[str, tuple[int, int]]:
    """address -> (capacity before, capacity after losing `zone`)."""
    return {w.address: (w.min_capacity if at == "min" else w.max_capacity, w.after_losing(zone, at)) for w in workloads(plan)}


def worst_case(plan: Plan, at: str = "min") -> dict[str, tuple[int, str]]:
    """address -> (lowest capacity left after any single zone loss, the zone that causes it)."""
    out: dict[str, tuple[int, str]] = {}
    for w in workloads(plan):
        best = None
        for z in ([UNKNOWN_ZONE] if UNKNOWN_ZONE in w.zones else []) + zones_in_play(plan):
            left = w.after_losing(z, at)
            if best is None or left < best[0]:
                best = (left, z)
        out[w.address] = best or (w.min_capacity, "")
    return out


def single_points_of_failure(plan: Plan) -> list[str]:
    """Workloads that go to zero when some single zone fails."""
    return [a for a, (left, _) in worst_case(plan).items() if left == 0]


# ------------------------------------------------------------------ region loss (lesson 22)
DUAL_REGIONS = {
    "NAM4": {"us-central1", "us-east1"},
    "EUR4": {"europe-north1", "europe-west4"},
    "EUR5": {"europe-west1", "europe-west2"},
    "EUR7": {"europe-west2", "europe-west3"},
    "ASIA1": {"asia-northeast1", "asia-northeast2"},
}
MULTI_REGIONS = {"US": "us-", "EU": "europe-", "ASIA": "asia-"}

UNLIMITED = 10 ** 9   # minutes: "this data is gone"


@dataclass
class DataStore:
    address: str
    kind: str                # "bucket" | "sql" | "registry" | "kms" | "secret"
    regions: set[str]        # regions holding a copy; {"*"} = global
    rpo_minutes: int         # data lost if the primary region disappears now


def bucket_regions(location: str, resource: Resource | None = None) -> set[str]:
    loc = str(location or "").upper()
    if loc in DUAL_REGIONS:
        return set(DUAL_REGIONS[loc])
    if loc in MULTI_REGIONS:
        return {f"{MULTI_REGIONS[loc]}*"}
    if resource is not None:
        custom = (resource.get("custom_placement_config") or [{}])[0].get("data_locations") or []
        if custom:
            return {str(c).lower() for c in custom}
    return {loc.lower()}


def data_stores(plan: Plan) -> list[DataStore]:
    out: list[DataStore] = []
    for b in plan.resources("google_storage_bucket"):
        regs = bucket_regions(b.get("location"), b)
        if len(regs) == 1 and not next(iter(regs)).endswith("*"):
            rpo = UNLIMITED
        else:
            rpo = 15 if b.get("rpo") == "ASYNC_TURBO" else 720
        out.append(DataStore(b.address, "bucket", regs, rpo))
    sql = plan.resources("google_sql_database_instance")
    # Primary vs replica comes from the configuration (prepared state may hold placeholder values).
    is_replica = lambda s: "master_instance_name" in (s.config.get("expressions") or {})
    primaries = [s for s in sql if not is_replica(s)]
    for p in primaries:
        replicas = [s for s in sql if is_replica(s) and (p in plan.linked(s, "google_sql_database_instance", "master_instance_name")
                    or s.get("master_instance_name") == p.get("name"))]
        regs = {p.get("region")} | {r.get("region") for r in replicas}
        backups = ((p.get("settings") or [{}])[0].get("backup_configuration") or [{}])[0]
        if len(regs) > 1:
            rpo = 1                                     # async cross-region replication: seconds
        elif backups.get("enabled"):
            rpo = 1440                                  # daily backups are stored multi-regionally
            loc = backups.get("location")
            regs = regs | ({f"{MULTI_REGIONS[loc.upper()]}*"} if loc and loc.upper() in MULTI_REGIONS else {"*backup"})
        else:
            rpo = UNLIMITED
        out.append(DataStore(p.address, "sql", {r for r in regs if r}, rpo))
    for r in plan.resources("google_artifact_registry_repository"):
        regs = bucket_regions(r.get("location"))
        out.append(DataStore(r.address, "registry", regs, 0 if len(regs) > 1 or next(iter(regs)).endswith("*") else UNLIMITED))
    return out


def lose_region(plan: Plan, region: str) -> dict[str, bool]:
    """address -> does a copy of this data store survive the loss of `region`?"""
    out = {}
    for s in data_stores(plan):
        others = {r for r in s.regions if r != region}
        multi = any(r.endswith("*") for r in s.regions)
        out[s.address] = bool(others) or multi
    return out
