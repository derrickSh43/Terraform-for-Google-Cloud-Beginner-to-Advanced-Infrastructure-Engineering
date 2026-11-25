"""Lesson 22 - Disaster Recovery and Business Continuity.

`plan` is dev against the deployed lesson 21 environment (DR is switched off there);
`plan.others["prod"]` is prod, which must survive the loss of its primary region.
Region-loss analysis: coursekit.failure.data_stores / lose_region.
"""

from coursekit import failure
from coursekit.checks import require, requirement

CRITICAL = {
    "database": lambda s: s.kind == "sql",
    "backups": lambda s: s.address == "module.foundation.google_storage_bucket.backups",
    "audit logs": lambda s: s.address == "module.observability.google_storage_bucket.audit",
    "images": lambda s: s.kind == "registry",
}
OBJECTIVES = {"database": "sql", "backups": "backups", "images": "registry"}


def _prod(plan):
    return plan.others["prod"]


def _regions(p):
    region, dr = p.variable_value("region"), p.variable_value("dr_region")
    return region, dr


def _store(p, pred, what):
    found = [s for s in failure.data_stores(p) if pred(s)]
    require(found, f"{p.name}: no {what} found")
    return found[0]


def _replicas(p):
    return [s for s in p.resources("google_sql_database_instance") if "master_instance_name" in (s.config.get("expressions") or {})]


def _primary(p):
    prim = [s for s in p.resources("google_sql_database_instance") if s not in _replicas(p)]
    require(prim, f"{p.name}: no primary Cloud SQL instance")
    return prim[0]


def _fmt(minutes):
    return "never (the data is gone)" if minutes >= failure.UNLIMITED else f"{minutes} min"


# ------------------------------------------------------------------ lab
@requirement("R22.1", "prod names a disaster-recovery region; dev has none",
             hint='variable "dr_region" (default null); prod terraform.tfvars: dr_region = "us-east1"')
def dr_region(plan):
    region, dr = _regions(_prod(plan))
    require(dr, "prod has no dr_region")
    require(dr != region, f"dr_region ({dr}) must differ from region ({region})")
    require(plan.variable_value("dr_region") is None, "dev sets dr_region - DR is a prod cost; keep dev cheap")


@requirement("R22.2", "A cross-region read replica of the prod database, private like its primary",
             hint="google_sql_database_instance.replica: master_instance_name = the primary's name, region = var.dr_region, ipv4_enabled = false, private_network = var.network_id")
def replica(plan):
    p = _prod(plan)
    reps = _replicas(p)
    require(reps, "prod has no Cloud SQL replica")
    r = reps[0]
    require(_primary(p) in p.linked(r, "google_sql_database_instance", "master_instance_name"),
            "The replica's master_instance_name must reference the primary instance")
    require(r.get("region") == p.variable_value("dr_region"), f"The replica is in {r.get('region')}, not the DR region")
    ipc = (((r.get("settings") or [{}])[0]).get("ip_configuration") or [{}])[0]
    require(ipc.get("ipv4_enabled") is False, "The replica has a public IP")
    require(ipc.get("private_network") or r.is_unknown("settings.0.ip_configuration.0.private_network"), "The replica has no private network")
    require(r.get("deletion_protection") is True, "Protect the replica from deletion: it's your recovery copy")


@requirement("R22.3", "prod backups live in a dual-region that covers both regions",
             hint='storage_location = "NAM4" (us-central1 + us-east1) for the backups bucket')
def backups_location(plan):
    p = _prod(plan)
    region, dr = _regions(p)
    s = _store(p, CRITICAL["backups"], "backups bucket")
    require({region, dr} <= s.regions or any(r.endswith("*") for r in s.regions),
            f"The backups bucket is stored in {sorted(s.regions)}: it must cover {region} and {dr}")


@requirement("R22.4", "Backups replicate within 15 minutes (turbo replication)",
             hint='rpo = "ASYNC_TURBO" on the dual-region backups bucket; the default replication can take up to 12 hours')
def turbo(plan):
    b = _prod(plan).resource("module.foundation.google_storage_bucket.backups")
    require(b is not None, "No backups bucket in prod")
    require(b.get("rpo") == "ASYNC_TURBO", f"rpo is {b.get('rpo') or 'DEFAULT'}")


@requirement("R22.5", "Customer-managed keys live where the buckets they encrypt live",
             hint="A CMEK key must be in the bucket's location: a NAM4 bucket needs a key ring in nam4")
def cmek_location(plan):
    for p in (plan, _prod(plan)):
        rings = {str(r.get("location") or "").lower() for r in p.resources("google_kms_key_ring")}
        bad = [f"{b.address} ({b.get('location')})" for b in p.resources("google_storage_bucket")
               if (b.blocks("encryption") or b.is_unknown("encryption")) and str(b.get("location") or "").lower() not in rings]
        require(not bad, f"{p.name}: CMEK buckets without a key ring in their location {sorted(rings)}: {bad} - the bucket creation would fail")


@requirement("R22.6", "Container images can be pulled after a region loss",
             hint='registry_location = "us" (multi-region) in prod')
def images(plan):
    p = _prod(plan)
    s = _store(p, CRITICAL["images"], "Artifact Registry repository")
    require(failure.lose_region(p, p.variable_value("region")).get(s.address),
            f"The repository is only in {sorted(s.regions)}: without images, nothing can be redeployed")


@requirement("R22.7", "Recovery objectives are written down, and the configuration can meet them",
             hint="recovery_objectives in prod terraform.tfvars: database (RPO 5), backups (RPO 15), images (RPO 0), each with an RTO")
def objectives(plan):
    p = _prod(plan)
    obj = p.variable_value("recovery_objectives") or {}
    missing = [k for k in OBJECTIVES if k not in obj]
    require(not missing, f"No recovery objectives for: {missing}")
    bad = []
    for name, kind in OBJECTIVES.items():
        target = obj[name]
        require(target.get("rto_minutes") is not None and target.get("rpo_minutes") is not None, f"{name}: set both rpo_minutes and rto_minutes")
        pred = CRITICAL["backups"] if kind == "backups" else (lambda s, k=kind: s.kind == k)
        store = _store(p, pred, name)
        if store.rpo_minutes > target["rpo_minutes"]:
            bad.append(f"{name}: RPO target {target['rpo_minutes']} min, but this configuration loses {_fmt(store.rpo_minutes)} of data in a region outage")
    require(not bad, "\n  ".join(bad))


@requirement("R22.8", "prod's critical data survives the loss of its primary region",
             hint="Database (replica), backups and audit logs (dual-region), images (multi-region)")
def region_loss(plan):
    p = _prod(plan)
    region = p.variable_value("region")
    survived = failure.lose_region(p, region)
    lost = []
    for name, pred in CRITICAL.items():
        stores = [s for s in failure.data_stores(p) if pred(s)]
        lost += [f"{name}: {s.address} only in {sorted(s.regions)}" for s in stores if not survived.get(s.address)]
    require(not lost, f"Lost with {region}:\n  " + "\n  ".join(lost))


@requirement("R22.9", "Deployed dev doesn't change: the DR footprint is switched off there",
             hint="Every new input defaults to the old behaviour (null / false): dev's plan shows no resource changes")
def dev_unchanged(plan):
    changed = [f"{r.address} ({'/'.join(r.actions)})" for r in plan.all_changes() if r.actions not in (["no-op"], ["read"])]
    require(not changed, "dev would change:\n  " + "\n  ".join(changed[:15]))


@requirement("R22.10", "prod and dev use the same modules",
             hint="Same module calls in both environments; only tfvars differ")
def same_modules(plan):
    srcs = lambda p: {n: c.get("source") for n, c in p.module_calls().items()}
    require(srcs(plan) == srcs(_prod(plan)), "dev and prod call different modules")


# ------------------------------------------------------------------ challenge
@requirement("C22.1", "The replica can take the full load after promotion",
             hint="Same tier as the primary, and deletion_protection_enabled in its settings", level="challenge")
def replica_ready(plan):
    p = _prod(plan)
    reps = _replicas(p)
    require(reps, "No replica")
    rs, ps = (reps[0].get("settings") or [{}])[0], (_primary(p).get("settings") or [{}])[0]
    require(rs.get("tier") == ps.get("tier"), f"Replica tier {rs.get('tier')} vs primary {ps.get('tier')}: after promotion it serves everything")
    require(rs.get("deletion_protection_enabled") is True, "Set deletion_protection_enabled (API-level protection) on the replica")


@requirement("C22.2", "The failover steps are generated from the configuration",
             hint='output "failover_commands": gcloud sql instances promote-replica <replica name>, and how to rebuild compute in var.dr_region',
             level="challenge")
def failover_output(plan):
    p = _prod(plan)
    out = (p.data.get("planned_values", {}).get("outputs", {}) or {}).get("failover_commands")
    require(out is not None, 'No output "failover_commands" in prod')
    text = " ".join(map(str, out.get("value") or []))
    rep = (_replicas(p) or [None])[0]
    require("promote-replica" in text, "The commands don't promote the replica")
    require(rep is not None and str(rep.get("name")) in text, "Use the replica's real name (module output), not a typed copy")
    require(p.variable_value("dr_region") in text, "Say where compute is rebuilt (var.dr_region)")


@requirement("C22.3", "Database backups are stored in a multi-region that includes the DR region",
             hint='backup_configuration { location = "us" } on the prod primary', level="challenge")
def backup_location(plan):
    p = _prod(plan)
    bc = (((_primary(p).get("settings") or [{}])[0]).get("backup_configuration") or [{}])[0]
    loc = str(bc.get("location") or "")
    require(loc and failure.bucket_regions(loc) and any(r.endswith("*") and p.variable_value("dr_region").startswith(r[:-1])
                                                         for r in failure.bucket_regions(loc)),
            f"backup location is {loc or 'Google default'}: set a multi-region covering {p.variable_value('dr_region')}")


@requirement("C22.4", "The postgres module refuses a 'DR' replica in the primary's own region",
             hint="validation: dr_region == null || dr_region != region; tests/challenge/modules/postgres must pass",
             level="challenge",
             test="replica.tftest.hcl")
def dr_validation(plan):
    var = next(iter(plan.source.blocks("variable", "dr_region", under="modules/postgres")), None)
    require(var is not None and var.block("validation") and "var.region" in var.body,
            "dr_region in modules/postgres needs a validation comparing it with var.region")
