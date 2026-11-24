"""Lesson 15 - Containers and Kubernetes (GKE).

`plan` is dev against the deployed lesson 14 environment.
"""

import ipaddress
import itertools
import re

from coursekit import iam
from coursekit.checks import require, requirement

WI_MEMBER = re.compile(r"^serviceAccount:(?P<pool>[^\[]+\.svc\.id\.goog)\[(?P<ns>[a-z0-9-]+)/(?P<ksa>[a-z0-9-]+)\]$")
PRIVATE = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]


def _cluster(plan):
    c = plan.resources("google_container_cluster")
    require(len(c) == 1, f"Expected one google_container_cluster, found {len(c)}")
    return c[0]


def _gke_subnet(plan, cluster):
    subs = plan.linked(cluster, "google_compute_subnetwork", "subnetwork")
    if not subs and cluster.get("subnetwork"):
        s = plan.find_by_id(cluster.get("subnetwork"))
        subs = [s] if s is not None else []
    require(len(subs) == 1, "The cluster's subnetwork is not a subnet managed in this configuration")
    return subs[0]


def _secondary(subnet):
    return {r.get("range_name"): r.get("ip_cidr_range") for r in subnet.get("secondary_ip_range") or []}


def _all_ranges(plan):
    """(label, network) for every primary/secondary subnet range, PSA range and GKE master range."""
    out = []
    for s in plan.resources("google_compute_subnetwork"):
        if s.get("ip_cidr_range"):
            out.append((f"subnet {s.get('name')}", ipaddress.ip_network(s.get("ip_cidr_range"), strict=False)))
        for name, cidr in _secondary(s).items():
            out.append((f"{s.get('name')}/{name}", ipaddress.ip_network(cidr, strict=False)))
    for a in plan.resources("google_compute_global_address"):
        if a.get("purpose") == "VPC_PEERING" and a.get("address"):
            out.append(("PSA range", ipaddress.ip_network(f"{a.get('address')}/{a.get('prefix_length')}", strict=False)))
    for c in plan.resources("google_container_cluster"):
        m = c.get("private_cluster_config.0.master_ipv4_cidr_block")
        if m:
            out.append(("GKE control plane", ipaddress.ip_network(m, strict=False)))
    return out


def _sa(plan, account_id):
    s = [x for x in plan.resources("google_service_account") if x.get("account_id") == account_id]
    return s[0] if s else None


# ------------------------------------------------------------------ lab
@requirement("R15.1", "The Kubernetes Engine API is enabled",
             hint="Add container.googleapis.com to the foundation APIs.")
def api(plan):
    require("container.googleapis.com" in {r.get("service") for r in plan.resources("google_project_service")},
            "container.googleapis.com is not enabled")


@requirement("R15.2", "A dedicated subnet with secondary ranges for pods and services, overlapping nothing",
             hint='subnets.gke (/22 for nodes) + secondary_ranges = { gke = { pods = "<.../17>", services = "<.../22>" } }')
def ranges(plan):
    c = _cluster(plan)
    s = _gke_subnet(plan, c)
    sec = _secondary(s)
    require(len(sec) >= 2, f"Subnet {s.get('name')} has secondary ranges {sorted(sec) or 'none'}: needs one for pods and one for services")
    others = [x.address for x in plan.resources("google_compute_instance") + plan.resources("google_compute_instance_template")
              if any(sub.address == s.address for sub in plan.linked(x, "google_compute_subnetwork", "network_interface.subnetwork"))]
    require(not others, f"The GKE subnet is shared with VMs ({others}) - give the cluster its own subnet")
    for (a, na), (b, nb) in itertools.combinations(_all_ranges(plan), 2):
        require(not na.overlaps(nb), f"{a} ({na}) overlaps {b} ({nb})")


@requirement("R15.3", "A regional Autopilot cluster, VPC-native on the subnet's named ranges",
             hint="enable_autopilot = true, location = var.region, ip_allocation_policy { cluster_secondary_range_name = \"pods\"  services_secondary_range_name = \"services\" }")
def cluster(plan):
    c = _cluster(plan)
    require(c.get("enable_autopilot") is True, "Use Autopilot: Google manages nodes, scaling and hardening")
    require(c.get("location") == plan.variable_value("region"), f"location {c.get('location')}: use the region (regional control plane)")
    ipa = c.get("ip_allocation_policy.0") or {}
    sec = _secondary(_gke_subnet(plan, c))
    for key in ("cluster_secondary_range_name", "services_secondary_range_name"):
        require(ipa.get(key) in sec, f"ip_allocation_policy.{key} = {ipa.get(key)!r} is not a secondary range of the GKE subnet {sorted(sec)}")
    require(ipa.get("cluster_secondary_range_name") != ipa.get("services_secondary_range_name"), "Pods and services need different ranges")


@requirement("R15.4", "Private nodes, private control plane, private authorized networks only",
             hint="private_cluster_config { enable_private_nodes = true  enable_private_endpoint = true }; master_authorized_networks_config with the ops range only")
def private(plan):
    c = _cluster(plan)
    pcc = c.get("private_cluster_config.0") or {}
    require(pcc.get("enable_private_nodes") is True, "Nodes would get external IPs")
    man = c.get("master_authorized_networks_config.0") or {}
    blocks = [b.get("cidr_block") for b in man.get("cidr_blocks") or []]
    public = [b for b in blocks if not any(ipaddress.ip_network(b, strict=False).subnet_of(p) for p in PRIVATE
                                           if ipaddress.ip_network(b, strict=False).version == 4)]
    require(not public, f"Authorized networks include public ranges {public} - the Kubernetes API would be reachable from the internet")
    require(pcc.get("enable_private_endpoint") is True, "The control plane still has a public endpoint (enable_private_endpoint = false)")
    require(blocks, "No master authorized networks: restrict the Kubernetes API to the ops VPC")


@requirement("R15.5", "Workload Identity, bound to one specific Kubernetes service account",
             hint='workload_identity_config { workload_pool = "<project>.svc.id.goog" } + roles/iam.workloadIdentityUser on a GSA for '
                  '"serviceAccount:<project>.svc.id.goog[batch/report-generator]"')
def workload_identity(plan):
    c = _cluster(plan)
    pool = c.get("workload_identity_config.0.workload_pool")
    project = plan.variable_value("project_id")
    require(pool == f"{project}.svc.id.goog", f"workload_pool is {pool!r}, expected '{project}.svc.id.goog'")
    wiu = [g for g in iam.grants(plan) if g.scope == "service_account" and g.role == "roles/iam.workloadIdentityUser"
           and ".svc.id.goog[" in g.principal]
    require(wiu, "No Google service account is bound to a Kubernetes service account")
    for g in wiu:
        m = WI_MEMBER.match(g.principal)
        require(m, f"{g.principal}: bind one namespace/KSA pair (no wildcards)")
        require(m.group("pool") == pool, f"{g.principal} uses a different pool than the cluster")


@requirement("R15.6", "Nodes run as a dedicated, minimal service account",
             hint="cluster_autoscaling.auto_provisioning_defaults.service_account = a dedicated SA with roles/container.defaultNodeServiceAccount "
                  "+ artifactregistry.reader on the repository")
def nodes(plan):
    c = _cluster(plan)
    sa_email = c.get("cluster_autoscaling.0.auto_provisioning_defaults.0.service_account")
    sas = plan.linked(c, "google_service_account", "cluster_autoscaling.auto_provisioning_defaults.service_account")
    require(sas or (sa_email and "-compute@developer" not in sa_email),
            "Nodes would run as the default compute service account (Editor)")
    require(sas, "The node service account is not managed in this configuration")
    grants = iam.for_principal(iam.grants(plan), f"sa:{sas[0].address}")
    project_roles = {g.role for g in grants if g.scope == "project"}
    require(project_roles == {"roles/container.defaultNodeServiceAccount"},
            f"Node SA project roles {sorted(project_roles)}: use only roles/container.defaultNodeServiceAccount")
    require(any(g.scope == "repository" and g.role == "roles/artifactregistry.reader" for g in grants),
            "Nodes can't pull from the Meridian registry - grant artifactregistry.reader on the repository")


@requirement("R15.7", "Upgrades are managed: release channel, weekend maintenance, deletion protection",
             hint='release_channel { channel = "REGULAR" }, maintenance_policy.recurring_window at weekends, deletion_protection = true')
def operations(plan):
    c = _cluster(plan)
    require(c.get("release_channel.0.channel") in ("RAPID", "REGULAR", "STABLE"), "Enrol in a release channel")
    rec = c.get("maintenance_policy.0.recurring_window.0.recurrence") or ""
    require("BYDAY" in rec, "Set a recurring maintenance window so upgrades happen when you choose")
    require(c.get("deletion_protection") is True, "deletion_protection must be true")


@requirement("R15.8", "The batch workload reads only the database secret, with no project roles",
             hint="workloads = { reports = \"batch/report-generator\" } and add its GSA to the db module's secret_readers")
def batch(plan):
    sa = _sa(plan, "meridian-reports")
    require(sa is not None, "No Google service account meridian-reports for the report-generator job")
    grants = iam.for_principal(iam.grants(plan), f"sa:{sa.address}")
    require(not [g for g in grants if g.scope == "project"], "meridian-reports must not have project-level roles")
    require(any(g.scope == "secret" and g.role == "roles/secretmanager.secretAccessor" for g in grants),
            "meridian-reports cannot read the database password secret")


@requirement("R15.9", "Deployed dev changes safely: additions only",
             hint="The dynamic secondary_ip_range block must leave the existing subnets unchanged.")
def safe(plan):
    bad = []
    for r in plan.all_changes():
        if r.is_replaced:
            bad.append(f"{r.address} would be REPLACED (forced by: " +
                       (", ".join(".".join(str(x) for x in p) for p in r.replace_paths) or "a force-new attribute") + ")")
        elif r.actions == ["delete"]:
            bad.append(f"{r.address} would be DESTROYED")
        elif r.actions == ["update"] and r.type == "google_compute_subnetwork":
            bad.append(f"{r.address} would be updated - existing subnets should not change")
    require(not bad, "Against the deployed dev environment:\n  " + "\n  ".join(bad))


@requirement("R15.10", "prod uses the STABLE channel and its own, non-overlapping ranges",
             hint='prod tfvars: gke_release_channel = "STABLE", 10.20.32.0/22 nodes, 10.21.0.0/17 pods, 10.21.128.0/22 services, its own /28 master range')
def prod(plan):
    prod = plan.others["prod"]
    srcs = lambda p: {n: c.get("source") for n, c in p.configuration.get("root_module", {}).get("module_calls", {}).items()}
    require(srcs(plan) == srcs(prod), "dev and prod call different modules")
    require(_cluster(prod).get("release_channel.0.channel") == "STABLE", "prod should use the STABLE release channel")
    for (a, na), (b, nb) in itertools.product(_all_ranges(plan), _all_ranges(prod)):
        if a == "GKE control plane" and b == "GKE control plane":
            require(not na.overlaps(nb), "dev and prod GKE control-plane ranges overlap")
        elif "control plane" not in a and "control plane" not in b:
            require(not na.overlaps(nb), f"dev {a} ({na}) overlaps prod {b} ({nb})")


# ------------------------------------------------------------------ challenge
@requirement("C15.1", "Only policy-approved images can run (Binary Authorization)",
             hint='binary_authorization { evaluation_mode = "PROJECT_SINGLETON_POLICY_ENFORCE" }', level="challenge")
def binauthz(plan):
    require(_cluster(plan).get("binary_authorization.0.evaluation_mode") == "PROJECT_SINGLETON_POLICY_ENFORCE",
            "Binary Authorization is not enforced")


@requirement("C15.2", "Workload vulnerability scanning is on",
             hint='security_posture_config { mode = "BASIC"  vulnerability_mode = "VULNERABILITY_BASIC" }', level="challenge")
def posture(plan):
    sp = _cluster(plan).get("security_posture_config.0") or {}
    require(sp.get("vulnerability_mode") in ("VULNERABILITY_BASIC", "VULNERABILITY_ENTERPRISE"), "Vulnerability scanning is off")


@requirement("C15.3", "Cluster costs are attributable",
             hint="cost_management_config { enabled = true } and resource_labels", level="challenge")
def costs(plan):
    c = _cluster(plan)
    require(c.get("cost_management_config.0.enabled") is True, "GKE cost allocation is off")
    require((c.get("resource_labels") or {}).get("env"), "Label the cluster (env, app...)")


@requirement("C15.4", "The module rejects public authorized networks",
             hint="validation on var.authorized_networks; tests/challenge/gke_module.tftest.hcl must pass", level="challenge")
def validation(plan):
    mods = plan.configuration.get("root_module", {}).get("module_calls", {})
    require(any("authorized_networks" in m.get("module", {}).get("variables", {}) for m in mods.values()),
            "No module declares authorized_networks")
