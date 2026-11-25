"""Lesson 11 - Cloud Storage and Persistent Data.

`plan` is dev against the deployed lesson 10 environment.
"""

from coursekit import iam
from coursekit.checks import require, requirement

DAY = 86400
OBJECT_WRITE_ROLES = {"roles/storage.objectCreator", "roles/storage.objectUser"}


def _app(plan):
    apps = plan.by_tag("app")
    require(len(apps) == 1, f'Expected one VM tagged "app", found {len(apps)}')
    return apps[0]


def _data_disk(plan):
    disks = plan.resources("google_compute_disk")
    require(len(disks) == 1, f"Expected one separate data disk (google_compute_disk), found {len(disks)}")
    return disks[0]


def _backups(plan):
    buckets = [b for b in plan.resources("google_storage_bucket") if b.blocks("retention_policy")]
    require(len(buckets) == 1, f"Expected one bucket with a retention_policy (backups), found {len(buckets)}")
    return buckets[0]


def _assets(plan):
    a = [b for b in plan.resources("google_storage_bucket") if (b.get("name") or "").endswith("-assets")]
    require(len(a) == 1, "Could not find the assets bucket")
    return a[0]


def _rules(bucket):
    out = []
    for r in bucket.blocks("lifecycle_rule"):
        out.append(((r.get("action") or [{}])[0], (r.get("condition") or [{}])[0]))
    return out


def _source_lifecycle(plan, rtype, attr):
    """Lifecycle settings of all `rtype` resource blocks in the tree's source."""
    vals = []
    for blk in plan.source.blocks("resource", rtype):
        lc = blk.block("lifecycle")
        if lc:
            vals.append((lc.attr(attr) or "").replace(" ", ""))
    return vals


def _snap_policy(plan):
    pols = [p for p in plan.resources("google_compute_resource_policy") if p.get("snapshot_schedule_policy")]
    require(len(pols) == 1, f"Expected one snapshot schedule (google_compute_resource_policy), found {len(pols)}")
    return pols[0]


# ------------------------------------------------------------------ lab
@requirement("R11.1", "The app tier has a separate data disk",
             hint='google_compute_disk: pd-balanced, 10-100 GB, in the app VM\'s zone, labelled')
def data_disk(plan):
    d = _data_disk(plan)
    app = _app(plan)
    require(d.get("type") in ("pd-balanced", "pd-ssd"), f"Disk type {d.get('type')}: use pd-balanced (or pd-ssd for databases)")
    size = int(d.get("size") or 0)
    require(10 <= size <= 100, f"Disk size {size} GB: 10-100 GB for this lab")
    require(d.get("zone") == app.get("zone"), f"The disk is in {d.get('zone')} but the app VM is in {app.get('zone')} - disks are zonal")
    require((d.get("labels") or {}).get("app") == "meridian", "Label the disk (app = meridian, env, ...)")


@requirement("R11.2", "The disk is attached with google_compute_attached_disk, and the VM ignores attached_disk",
             hint="google_compute_attached_disk { disk, instance } + lifecycle { ignore_changes = [attached_disk] } on the instance")
def attached(plan):
    d = _data_disk(plan)
    att = plan.resources("google_compute_attached_disk")
    require(att, "No google_compute_attached_disk - attach the disk without editing the deployed instance")
    a = att[0]
    require(any(x.address == d.address for x in plan.linked(a, "google_compute_disk", "disk")), "The attachment does not reference the data disk")
    require(plan.linked(a, "google_compute_instance", "instance"), "The attachment does not reference the app VM")
    ignores = _source_lifecycle(plan, "google_compute_instance", "ignore_changes")
    require(any("attached_disk" in v for v in ignores),
            "The instance must ignore_changes = [attached_disk], or every plan tries to detach the disk again")


@requirement("R11.3", "Daily snapshots, kept for a bounded time, that survive disk deletion",
             hint="google_compute_resource_policy (snapshot_schedule_policy: daily, max_retention_days 7-30, KEEP_AUTO_SNAPSHOTS) "
                  "+ google_compute_disk_resource_policy_attachment")
def snapshots(plan):
    p = _snap_policy(plan)
    sched = p.get("snapshot_schedule_policy.0") or {}
    s = (sched.get("schedule") or [{}])[0]
    require(s.get("daily_schedule") or s.get("hourly_schedule"), "Schedule snapshots at least daily")
    ret = (sched.get("retention_policy") or [{}])[0]
    days = int(ret.get("max_retention_days") or 0)
    require(7 <= days <= 30, f"max_retention_days = {days}: keep 7-30 days of daily snapshots")
    require(ret.get("on_source_disk_delete") == "KEEP_AUTO_SNAPSHOTS",
            "on_source_disk_delete must be KEEP_AUTO_SNAPSHOTS - otherwise deleting the disk deletes its backups too")
    d = _data_disk(plan)
    att = plan.resources("google_compute_disk_resource_policy_attachment")
    linked_disks = {x.address for a in att for x in plan.linked(a, "google_compute_disk", "disk")}
    require(d.address in linked_disks or d.get("resource_policies"), "The snapshot schedule is not attached to the data disk")


@requirement("R11.4", "Terraform refuses to destroy the data disk",
             hint="lifecycle { prevent_destroy = true } on the google_compute_disk resource")
def protect_disk(plan):
    _data_disk(plan)
    require(any(v == "true" for v in _source_lifecycle(plan, "google_compute_disk", "prevent_destroy")),
            "The data disk has no lifecycle { prevent_destroy = true }")


@requirement("R11.5", "A hardened backups bucket with an (unlocked) retention policy",
             hint='"${project}-backups": uniform access, public access prevention, retention_policy { retention_period = days * 86400  is_locked = false }')
def backups_bucket(plan):
    b = _backups(plan)
    require(b.get("uniform_bucket_level_access") is True, "Enable uniform bucket-level access")
    require(b.get("public_access_prevention") == "enforced", "Backups must never be public: public_access_prevention = \"enforced\"")
    rp = b.get("retention_policy.0") or {}
    secs = int(rp.get("retention_period") or 0)
    require(secs >= 7 * DAY, f"Retention is {secs // DAY} days: keep backups at least 7 days")
    require(rp.get("is_locked") is not True, "Don't lock retention in dev - locking is irreversible (see the challenge for prod)")
    require(not (b.get("versioning") or [{}])[0].get("enabled"), "Retention policies and Object Versioning can't be combined")
    require(b.get("force_destroy") is not True, "force_destroy must be false on a backups bucket")


@requirement("R11.6", "Backups get cheaper as they age, then expire",
             hint="lifecycle_rule: SetStorageClass NEARLINE at age 30, COLDLINE at age 90, Delete at age 365 (>= retention)")
def tiering(plan):
    b = _backups(plan)
    rules = _rules(b)
    def age_for(kind, cls=None):
        ages = [int(c.get("age")) for a, c in rules if a.get("type") == kind and (cls is None or a.get("storage_class") == cls) and c.get("age")]
        return min(ages) if ages else None
    nl, cl, de = age_for("SetStorageClass", "NEARLINE"), age_for("SetStorageClass", "COLDLINE"), age_for("Delete")
    require(nl is not None and nl >= 30, f"NEARLINE transition at age {nl}: Nearline has a 30-day minimum, so move objects at >= 30 days")
    require(cl is not None and cl >= 90 and cl > nl, f"COLDLINE transition at age {cl}: after Nearline, at >= 90 days")
    retention_days = int((b.get("retention_policy.0") or {}).get("retention_period") or 0) // DAY
    require(de is not None and de >= retention_days, f"Delete at age {de}: must not be before the retention period ({retention_days} days)")


@requirement("R11.7", "The assets bucket expires old object versions",
             hint="lifecycle_rule { condition { days_since_noncurrent_time = 30 }  action { type = \"Delete\" } } on the assets bucket")
def assets_noncurrent(plan):
    ok = False
    for a, c in _rules(_assets(plan)):
        days = c.get("days_since_noncurrent_time") or c.get("num_newer_versions")
        if a.get("type") == "Delete" and days and int(days) <= 90:
            ok = True
    require(ok, "Versioning keeps every overwrite forever - delete noncurrent versions within 90 days")


@requirement("R11.8", "Deployed dev changes safely: nothing destroyed or replaced",
             hint="The app VM must not be recreated: attach the disk with a separate resource and ignore_changes.")
def safe(plan):
    bad = []
    for r in plan.all_changes():
        if r.is_replaced:
            why = ", ".join(".".join(str(x) for x in p) for p in r.replace_paths) or "a force-new attribute"
            bad.append(f"{r.address} would be REPLACED (forced by: {why})")
        elif r.actions == ["delete"]:
            bad.append(f"{r.address} would be DESTROYED")
    require(not bad, "Against the deployed dev environment:\n  " + "\n  ".join(bad))


@requirement("R11.9", "The app writes backups with a bucket-level, create-only role",
             hint='writable_buckets = [module.foundation.backups_bucket] -> roles/storage.objectCreator on that bucket')
def app_backup_access(plan):
    sas = [s for s in plan.resources("google_service_account") if s.get("account_id") == "meridian-app"]
    require(sas, "meridian-app service account not found")
    grants = iam.for_principal(iam.grants(plan), f"sa:{sas[0].address}")
    b = _backups(plan)
    on_backups = [g for g in grants if g.scope == "bucket" and
                  ((g.target is not None and g.target.address == b.address) or g.target_name == b.get("name"))]
    require(on_backups, "meridian-app has no access to the backups bucket")
    require(all(g.role in OBJECT_WRITE_ROLES for g in on_backups),
            f"meridian-app holds {[g.role for g in on_backups]} on backups - writers don't need to read, list or delete")
    require(not [g for g in grants if g.scope == "project" and g.role.startswith("roles/storage.")], "No project-wide storage roles for meridian-app")


@requirement("R11.10", "prod keeps backups and snapshots longer",
             hint="prod tfvars: backup_retention_days >= 30, snapshot_retention_days >= dev's")
def prod(plan):
    prod = plan.others["prod"]
    srcs = lambda p: {n: c.get("source") for n, c in p.configuration.get("root_module", {}).get("module_calls", {}).items()}
    require(srcs(plan) == srcs(prod), "dev and prod call different modules")
    def keep(p):
        bs = [b for b in p.resources("google_storage_bucket") if b.blocks("retention_policy")]
        require(bs, f"{p.name} has no backups bucket")
        return int((bs[0].get("retention_policy.0") or {}).get("retention_period") or 0) // DAY
    def snap(p):
        pols = [x for x in p.resources("google_compute_resource_policy") if x.get("snapshot_schedule_policy")]
        require(pols, f"{p.name} has no snapshot schedule")
        return int(((pols[0].get("snapshot_schedule_policy.0") or {}).get("retention_policy") or [{}])[0].get("max_retention_days") or 0)
    require(keep(prod) >= 30 and keep(prod) >= keep(plan), f"prod keeps backups {keep(prod)} days - at least 30 and at least dev's {keep(plan)}")
    require(snap(prod) >= snap(plan), f"prod snapshot retention ({snap(prod)}d) is shorter than dev's ({snap(plan)}d)")


# ------------------------------------------------------------------ challenge
@requirement("C11.1", "prod locks backup retention; dev doesn't",
             hint="lock_backup_retention variable -> retention_policy.is_locked, true only in prod", level="challenge")
def locked(plan):
    def is_locked(p):
        bs = [b for b in p.resources("google_storage_bucket") if b.blocks("retention_policy")]
        return bool(bs and (bs[0].get("retention_policy.0") or {}).get("is_locked"))
    require(is_locked(plan.others["prod"]), "prod retention is not locked")
    require(not is_locked(plan), "dev retention must stay unlocked - a locked policy can never be removed")


@requirement("C11.2", "prod backups survive a regional outage (dual-region)",
             hint='location = "US" + custom_placement_config { data_locations = ["US-CENTRAL1", "US-EAST1"] }', level="challenge")
def dual_region(plan):
    bs = [b for b in plan.others["prod"].resources("google_storage_bucket") if b.blocks("retention_policy")]
    require(bs, "prod has no backups bucket")
    b = bs[0]
    locs = (b.get("custom_placement_config.0") or {}).get("data_locations") or []
    require(len(locs) == 2 or str(b.get("location")).upper() in ("NAM4", "EUR4", "ASIA1"),
            f"prod backups are in {b.get('location')} {locs} - use a dual-region")
    dev_b = _backups(plan)
    require(not (dev_b.get("custom_placement_config") or []), "dev doesn't need dual-region backups (cost)")


@requirement("C11.3", "Snapshots are stored multi-regionally",
             hint='snapshot_properties { storage_locations = ["us"] }', level="challenge")
def snap_location(plan):
    props = ((_snap_policy(plan).get("snapshot_schedule_policy.0") or {}).get("snapshot_properties") or [{}])[0]
    locs = props.get("storage_locations") or []
    require(any(l.lower() in ("us", "eu", "asia") for l in locs), f"Snapshot storage_locations {locs or 'not set'}: use a multi-region")


@requirement("C11.4", "vm-service validates the data disk size",
             hint="validation: 0 or 10-1000 GB; tests/challenge/vm_service_disk.tftest.hcl must pass", level="challenge",
             test="vm_service_disk.tftest.hcl")
def disk_validation(plan):
    mods = plan.configuration.get("root_module", {}).get("module_calls", {})
    require(any("data_disk_size_gb" in m.get("module", {}).get("variables", {}) for m in mods.values()), "No module declares data_disk_size_gb")
