"""Lesson 12 - Databases and Data Infrastructure.

`plan` is dev against the deployed lesson 11 environment.
"""

import ipaddress
import re

from coursekit import iam
from coursekit.checks import require, requirement
from coursekit.firewall import Firewall

APIS = {"sqladmin.googleapis.com", "servicenetworking.googleapis.com", "secretmanager.googleapis.com"}
SHARED_CORE = {"db-f1-micro", "db-g1-small"}
SECRET_ATTRS = ("result", "secret_data", "password", "private_key")


def _sql(plan):
    s = plan.resources("google_sql_database_instance")
    require(len(s) == 1, f"Expected one google_sql_database_instance, found {len(s)}")
    return s[0]


def _settings(inst):
    return inst.get("settings.0") or {}


def _psa(plan):
    a = [g for g in plan.resources("google_compute_global_address") if g.get("purpose") == "VPC_PEERING"]
    require(len(a) == 1, f"Expected one global address with purpose VPC_PEERING (Private Service Access range), found {len(a)}")
    return a[0]


def _psa_net(addr):
    return ipaddress.ip_network(f"{addr.get('address')}/{addr.get('prefix_length')}", strict=False)


def _sa(plan, account_id):
    s = [x for x in plan.resources("google_service_account") if x.get("account_id") == account_id]
    require(s, f"Service account {account_id} not found")
    return s[0]


def _secret(plan):
    s = plan.resources("google_secret_manager_secret")
    require(len(s) == 1, f"Expected one Secret Manager secret, found {len(s)}")
    return s[0]


def _main_vpc_id(plan):
    fw = Firewall(plan)
    web = [t for t in plan.resources("google_compute_instance_template") if "web" in (t.get("tags") or [])]
    net = fw.instance(web[0]).network if web else None
    vpc = plan.resource(net) if net else None
    return vpc.get("id") if vpc is not None else None


# ------------------------------------------------------------------ lab
@requirement("R12.1", "Cloud SQL, Service Networking and Secret Manager APIs are enabled",
             hint="Add sqladmin, servicenetworking and secretmanager .googleapis.com to the foundation module's APIs.")
def apis(plan):
    enabled = {r.get("service") for r in plan.resources("google_project_service")}
    missing = APIS - enabled
    require(not missing, "Missing APIs: " + ", ".join(sorted(missing)))


@requirement("R12.2", "Private Service Access: a reserved range peered with Google's service network",
             hint='google_compute_global_address (purpose = "VPC_PEERING", INTERNAL, /16-/24) + google_service_networking_connection '
                  '(service = "servicenetworking.googleapis.com", reserved_peering_ranges = [the range name])')
def psa(plan):
    a = _psa(plan)
    require(a.get("address_type") == "INTERNAL", "The PSA range must be INTERNAL")
    plen = int(a.get("prefix_length") or 0)
    require(16 <= plen <= 24, f"prefix_length /{plen}: use /16-/24 (Google recommends at least /24 per service, /16 for growth)")
    if a.get("address"):
        net = _psa_net(a)
        for s in plan.resources("google_compute_subnetwork"):
            sn = ipaddress.ip_network(s.get("ip_cidr_range"), strict=False)
            require(not net.overlaps(sn), f"The PSA range {net} overlaps subnet {s.get('name')} ({sn})")
    conns = plan.resources("google_service_networking_connection")
    require(len(conns) == 1, "Expected one google_service_networking_connection")
    c = conns[0]
    require(c.get("service") == "servicenetworking.googleapis.com", f"Connection service is {c.get('service')}")
    require(c.references_type("google_compute_global_address", "reserved_peering_ranges"),
            "reserved_peering_ranges should reference the reserved range resource")
    main = _main_vpc_id(plan)
    require(main is None or c.get("network") in (None, main), "The connection is not on the main Meridian VPC")


@requirement("R12.3", "The database has no public IP and requires TLS",
             hint='ip_configuration { ipv4_enabled = false  private_network = <PSA network>  ssl_mode = "ENCRYPTED_ONLY" }')
def private_db(plan):
    inst = _sql(plan)
    ver = inst.get("database_version", "")
    m = re.match(r"POSTGRES_(\d+)", ver)
    require(m and int(m.group(1)) >= 15, f"database_version {ver}: use PostgreSQL 15 or newer")
    ipc = (_settings(inst).get("ip_configuration") or [{}])[0]
    nets = ipc.get("authorized_networks") or []
    require(ipc.get("ipv4_enabled") is False, "ipv4_enabled is not false: the instance would get a public IP"
            + (f" open to {[n.get('value') for n in nets]}" if nets else ""))
    require(not nets, f"authorized_networks {[n.get('value') for n in nets]} - private instances need none")
    require(ipc.get("private_network") or inst.is_unknown("settings.0.ip_configuration.0.private_network"),
            "No private_network: the instance would be unreachable")
    require(ipc.get("ssl_mode") in ("ENCRYPTED_ONLY", "TRUSTED_CLIENT_CERTIFICATE_REQUIRED"),
            f"ssl_mode is {ipc.get('ssl_mode') or 'unset'} - require encrypted connections")


@requirement("R12.4", "Daily backups with point-in-time recovery",
             hint="backup_configuration { enabled = true  point_in_time_recovery_enabled = true  transaction_log_retention_days = 7  "
                  "backup_retention_settings { retained_backups = 7 } }")
def backups(plan):
    b = (_settings(_sql(plan)).get("backup_configuration") or [{}])[0]
    require(b.get("enabled") is True, "Automated backups are off")
    require(b.get("point_in_time_recovery_enabled") is True,
            "Point-in-time recovery is off: you could only restore to last night, losing up to a day of orders")
    require(int(b.get("transaction_log_retention_days") or 0) >= 3, "Keep transaction logs >= 3 days for PITR")
    kept = int(((b.get("backup_retention_settings") or [{}])[0]).get("retained_backups") or 0)
    require(kept >= 7, f"retained_backups = {kept}: keep at least 7")


@requirement("R12.5", "The instance can't be deleted by accident - in Terraform or the console",
             hint="deletion_protection = true (Terraform) and settings.deletion_protection_enabled = true (API)")
def protection(plan):
    inst = _sql(plan)
    require(inst.get("deletion_protection") is True, "deletion_protection (Terraform-level) is not true")
    require(_settings(inst).get("deletion_protection_enabled") is True,
            "settings.deletion_protection_enabled is not true - someone could still delete it in the console")


def _sensitive_refs(plan, module, refs):
    bad = []
    for ref in refs:
        for rref, _mod in plan.expand_ref(ref, module):
            bits = rref.split(".")
            if bits[0] == "random_password" or (len(bits) >= 3 and bits[2].split("[")[0] in SECRET_ATTRS):
                bad.append(rref)
    return bad


@requirement("R12.6", "Credentials are generated, stored in Secret Manager, and never exposed",
             hint="random_password (>= 20 chars) -> google_sql_user.password and google_secret_manager_secret_version.secret_data. "
                  "No output or tfvars may contain a password.")
def credentials(plan):
    pw = plan.resources("random_password")
    require(pw, "No random_password - passwords must be generated, not typed")
    require(all(int(p.get("length") or 0) >= 20 for p in pw), "Generate passwords of at least 20 characters")
    users = [u for u in plan.resources("google_sql_user") if (u.get("type") or "BUILT_IN") == "BUILT_IN"]
    require(users, "No password-based database user for the app")
    for u in users:
        require(u.constant("password") is None, f"{u.address} has a hard-coded password")
        require(u.references_type("random_password", "password"), f"{u.address} password does not come from random_password")
    versions = plan.resources("google_secret_manager_secret_version")
    require(versions and any(v.references_type("random_password", "secret_data") for v in versions),
            "The generated password is not stored in a Secret Manager secret version")
    leaks = [f'output "{name}" -> {", ".join(b)}' for name in plan.outputs()
             for b in [_sensitive_refs(plan, "", plan.output_references(name))] if b]
    require(not leaks, "Outputs expose secret material (even sensitive = true outputs end up in state and CI logs):\n  " + "\n  ".join(leaks))
    for path, text in plan.source.tfvars().items():
        for line in text.splitlines():
            if re.match(r'\s*\w*(password|secret|token)\w*\s*=\s*"[^"]+"', line, re.I):
                require(False, f"{path} contains a credential: {line.strip()[:40]}...")


@requirement("R12.7", "Only the app can read the password, through a secret-level grant",
             hint='google_secret_manager_secret_iam_member on the secret: role = "roles/secretmanager.secretAccessor", member = the app SA')
def secret_access(plan):
    secret = _secret(plan)
    grants = iam.grants(plan)
    app = _sa(plan, "meridian-app")
    on_secret = [g for g in grants if g.scope == "secret" and g.target is not None and g.target.address == secret.address]
    require(any(g.principal == f"sa:{app.address}" and g.role == "roles/secretmanager.secretAccessor" for g in on_secret),
            "meridian-app cannot read the password secret")
    others = [g.principal for g in on_secret if g.principal != f"sa:{app.address}"]
    require(not others, f"Other principals can read the password: {others}")
    project_wide = [f"{g.principal} has {g.role}" for g in grants if g.scope == "project" and g.role.startswith("roles/secretmanager.")]
    require(not project_wide, "Project-level Secret Manager roles reach every secret:\n  " + "\n  ".join(project_wide))


@requirement("R12.8", "The app tier can reach the database",
             hint='roles/cloudsql.client for meridian-app; egress from the app VM to the PSA range on 5432 must be allowed')
def app_reaches_db(plan):
    app = _sa(plan, "meridian-app")
    roles = {g.role for g in iam.for_principal(iam.grants(plan), f"sa:{app.address}", "project")}
    require("roles/cloudsql.client" in roles, "meridian-app lacks roles/cloudsql.client (needed by the Cloud SQL connectors)")
    a = _psa(plan)
    fw = Firewall(plan)
    vms = plan.by_tag("app")
    require(vms, "No app VM")
    ip = str(_psa_net(a)[3]) if a.get("address") else "10.10.16.3"
    v = fw.evaluate(fw.instance(vms[0], "app VM"), fw.ip(ip), "tcp", 5432)
    require(v.allowed, f"app VM -> {ip}:5432 is blocked ({v.reason})")


@requirement("R12.9", "Deployed dev changes safely: additions only",
             hint="Nothing that exists should be replaced or destroyed.")
def safe(plan):
    bad = []
    for r in plan.all_changes():
        if r.is_replaced:
            bad.append(f"{r.address} would be REPLACED (forced by: " +
                       (", ".join(".".join(str(x) for x in p) for p in r.replace_paths) or "a force-new attribute") + ")")
        elif r.actions == ["delete"]:
            bad.append(f"{r.address} would be DESTROYED")
    require(not bad, "Against the deployed dev environment:\n  " + "\n  ".join(bad))


@requirement("R12.10", "prod runs highly available on a dedicated tier; dev stays small",
             hint='prod tfvars: db_availability_type = "REGIONAL", db_tier = "db-custom-2-7680"; dev ZONAL on db-g1-small')
def prod(plan):
    prod = plan.others["prod"]
    p, d = _sql(prod), _sql(plan)
    ps, ds = _settings(p), _settings(d)
    require(ps.get("availability_type") == "REGIONAL", "prod Cloud SQL must be REGIONAL (standby in a second zone)")
    require(ps.get("tier") not in SHARED_CORE, f"prod tier {ps.get('tier')} is shared-core - no SLA, unsuitable for production")
    require(ds.get("availability_type", "ZONAL") == "ZONAL", "dev doesn't need REGIONAL (it doubles the cost)")
    pk = int((((ps.get("backup_configuration") or [{}])[0].get("backup_retention_settings")) or [{}])[0].get("retained_backups") or 0)
    dk = int((((ds.get("backup_configuration") or [{}])[0].get("backup_retention_settings")) or [{}])[0].get("retained_backups") or 0)
    require(pk >= dk, f"prod keeps fewer backups ({pk}) than dev ({dk})")
    pa, da = _psa(prod), _psa(plan)
    if pa.get("address") and da.get("address"):
        require(not _psa_net(pa).overlaps(_psa_net(da)), "dev and prod PSA ranges overlap")
        for s in prod.resources("google_compute_subnetwork"):
            require(not _psa_net(pa).overlaps(ipaddress.ip_network(s.get("ip_cidr_range"), strict=False)),
                    f"prod PSA range overlaps subnet {s.get('name')}")


# ------------------------------------------------------------------ challenge
def _flags(inst):
    return {f.get("name"): f.get("value") for f in _settings(inst).get("database_flags") or []}


@requirement("C12.1", "Slow queries are logged and Query Insights is on",
             hint='database_flags log_min_duration_statement = "500"; insights_config { query_insights_enabled = true }', level="challenge")
def observability(plan):
    inst = _sql(plan)
    v = _flags(inst).get("log_min_duration_statement")
    require(v is not None and 100 <= int(v) <= 10000, f"log_min_duration_statement = {v}: log queries slower than 100-10000 ms")
    ins = (_settings(inst).get("insights_config") or [{}])[0]
    require(ins.get("query_insights_enabled") is True, "Query Insights is off")


@requirement("C12.2", "The app logs in with IAM database authentication (passwordless)",
             hint='flag cloudsql.iam_authentication = "on" + google_sql_user type CLOUD_IAM_SERVICE_ACCOUNT for meridian-app', level="challenge")
def iam_auth(plan):
    inst = _sql(plan)
    require(_flags(inst).get("cloudsql.iam_authentication") == "on", "cloudsql.iam_authentication flag is not on")
    iam_users = [u for u in plan.resources("google_sql_user") if u.get("type") == "CLOUD_IAM_SERVICE_ACCOUNT"]
    require(iam_users, "No CLOUD_IAM_SERVICE_ACCOUNT database user")
    require(any(str(u.get("name", "")).startswith("meridian-app@") or u.is_unknown("name") for u in iam_users),
            "The IAM database user should be meridian-app (email without .gserviceaccount.com)")


@requirement("C12.3", "The secret's payload stays in named regions",
             hint="replication { user_managed { replicas { location = \"us-central1\" } replicas { location = \"us-east1\" } } }", level="challenge")
def residency(plan):
    rep = (_secret(plan).get("replication") or [{}])[0]
    um = (rep.get("user_managed") or [{}])[0]
    locs = [r.get("location") for r in um.get("replicas") or []]
    require(len(locs) >= 2, f"Secret replication is {'automatic' if rep.get('auto') else locs}: use user_managed with at least two named regions")


@requirement("C12.4", "The postgres module rejects HA on shared-core tiers",
             hint="cross-variable validation; tests/challenge/postgres_module.tftest.hcl must pass", level="challenge")
def ha_validation(plan):
    mods = plan.configuration.get("root_module", {}).get("module_calls", {})
    require(any("availability_type" in m.get("module", {}).get("variables", {}) for m in mods.values()),
            "No module declares availability_type")
