"""Lesson 06 - Terraform State and Reusable Code: requirement checks.

`plan` is the dev environment, planned against the deployed lesson 05 state
(state/dev.tfstate). Sibling roots: plan.others["prod"], plan.others["bootstrap"].
`plan.source` gives the HCL of the whole tree for facts the plan JSON omits.
"""

import ipaddress
import itertools

from coursekit.checks import require, requirement
from coursekit.firewall import Firewall
from coursekit.plan import strip_index

ENV_ROOTS = ("dev", "prod")


def _env(plan, name):
    return plan if name == plan.name else plan.others[name]


def _backend(plan, env):
    root = _env(plan, env).root
    be = plan.source.backend(root)
    require(be is not None, f"{root} has no backend block - its state would stay on one laptop")
    require(be.labels and be.labels[0] == "gcs", f"{root} uses backend \"{be.labels[0] if be.labels else '?'}\", expected \"gcs\"")
    return be


def _state_bucket(plan):
    boot = plan.others["bootstrap"]
    buckets = boot.resources("google_storage_bucket")
    require(len(buckets) == 1, f"bootstrap should create exactly one bucket (the state bucket), found {len(buckets)}")
    return buckets[0]


def _module_calls(plan):
    return plan.configuration.get("root_module", {}).get("module_calls", {})


def _walk_module_configs(module_cfg, path="root"):
    for name, call in module_cfg.get("module_calls", {}).items():
        mod = call.get("module", {})
        yield f"{path}/{name}", call.get("source", ""), mod
        yield from _walk_module_configs(mod, f"{path}/{name}")


# ------------------------------------------------------------------ lab
@requirement("R6.1", "dev and prod keep remote state in GCS, one prefix each",
             hint='envs/<env>/backend.tf: terraform { backend "gcs" { bucket = "<state bucket>"  prefix = "envs/<env>" } }')
def remote_state(plan):
    dev, prod = _backend(plan, "dev"), _backend(plan, "prod")
    for env, be in (("dev", dev), ("prod", prod)):
        require(be.attr("bucket"), f"{env} backend has no bucket")
        require(be.attr("prefix"), f"{env} backend has no prefix - environments would overwrite each other's state")
    require(dev.attr("prefix") != prod.attr("prefix"),
            f"dev and prod use the same prefix '{dev.attr('prefix')}' - they would share (and corrupt) one state file")
    require(dev.attr("bucket") == prod.attr("bucket"), "Use one state bucket for both environments (different prefixes)")


@requirement("R6.2", "bootstrap creates a hardened, versioned state bucket that the backends use",
             hint="bootstrap/main.tf: one google_storage_bucket with versioning, uniform access, public access prevention")
def state_bucket(plan):
    b = _state_bucket(plan)
    require((b.get("versioning") or [{}])[0].get("enabled") is True,
            "State bucket versioning is off - a bad apply or corrupted state couldn't be rolled back")
    require(b.get("uniform_bucket_level_access") is True, "State bucket needs uniform_bucket_level_access = true")
    require(b.get("public_access_prevention") == "enforced", "State contains secrets: public_access_prevention must be \"enforced\"")
    name = b.get("name")
    if name:
        backend_bucket = _backend(plan, "dev").attr("bucket")
        require(backend_bucket == name, f"Backends point at bucket '{backend_bucket}' but bootstrap creates '{name}'")


@requirement("R6.3", "The state bucket can't be destroyed by accident",
             hint="Inside the bucket resource: lifecycle { prevent_destroy = true }")
def prevent_destroy(plan):
    _state_bucket(plan)
    found = False
    for res in plan.source.blocks("resource", "google_storage_bucket", under="bootstrap"):
        lc = res.block("lifecycle")
        if lc and (lc.attr("prevent_destroy") or "").lower() == "true":
            found = True
    require(found, "The state bucket has no lifecycle { prevent_destroy = true }")


@requirement("R6.4", "Environment roots only wire modules together",
             hint="Move every resource block from envs/*/ into a module under modules/.")
def roots_only_modules(plan):
    for env in ENV_ROOTS:
        p = _env(plan, env)
        root_resources = [r["address"] for r in p.configuration.get("root_module", {}).get("resources", [])
                          if r.get("mode") == "managed"]
        require(not root_resources, f"{p.root} still declares resources directly: " + ", ".join(root_resources))
        require(_module_calls(p), f"{p.root} calls no modules")


@requirement("R6.5", "Infrastructure is split into local child modules",
             hint='module "network" { source = "../../modules/network" ... } - at least four modules.')
def local_modules(plan):
    calls = _module_calls(plan)
    require(len(calls) >= 4, f"Expected at least 4 module calls in envs/dev (foundation, network, firewall, VMs...), found {len(calls)}")
    for name, call in calls.items():
        src = call.get("source", "")
        require(src.startswith("../../modules/"), f'module "{name}" has source "{src}" - use a local module under ../../modules/')
    types_by_module = {}
    for r in plan.resources():
        top = r.module.split(".")[1] if r.module else ""
        types_by_module.setdefault(top, set()).add(r.type)
    require("google_compute_network" in set().union(*types_by_module.values()), "No VPC found in any module")
    net_mod = next((m for m, t in types_by_module.items() if "google_compute_network" in t), "")
    require("google_compute_instance" not in types_by_module.get(net_mod, set()),
            f'module "{net_mod}" mixes networking and VMs - give each concern its own module')


@requirement("R6.6", "One VM module is reused for both the web and app tiers",
             hint="Write the service-account + IAM + VM pattern once (e.g. modules/vm-service) and call it twice.")
def reused_vm_module(plan):
    vms = plan.resources("google_compute_instance")
    require(len(vms) == 2, f"Expected 2 VMs (web and app), found {len(vms)}")
    calls = _module_calls(plan)
    sources = {}
    for vm in vms:
        require(vm.module, f"{vm.address} is not inside a module")
        top = vm.module.split(".")[1]
        sources[vm.address] = calls.get(top, {}).get("source", "")
    srcs = set(sources.values())
    require(len(srcs) == 1, "web and app VMs come from different module sources (" + ", ".join(sorted(srcs)) + ") - reuse one module")
    tags = sorted(t for vm in vms for t in (vm.get("tags") or []))
    require("web" in tags and "app" in tags, f"The two VMs should be tagged web and app, got {tags}")


@requirement("R6.7", "Every module variable and output is documented",
             hint="Add description = \"...\" to each variable and output in modules/*/")
def documented(plan):
    mods = list(_walk_module_configs(plan.configuration.get("root_module", {})))
    require(mods, "envs/dev calls no modules yet")
    for path, src, mod in mods:
        for vname, v in mod.get("variables", {}).items():
            require(v.get("description"), f'{src}: variable "{vname}" has no description')
        for oname, o in mod.get("outputs", {}).items():
            require(o.get("description"), f'{src}: output "{oname}" has no description')


@requirement("R6.8", "The refactor is safe: deployed dev would not be destroyed or recreated",
             hint="Add moved { from = <old address>  to = <new address> } for every lesson 05 resource (envs/dev/moved.tf).")
def safe_refactor(plan):
    changes = plan.all_changes()
    deleted = [r for r in changes if r.actions == ["delete"]]
    created = [r for r in changes if r.actions == ["create"]]
    replaced = [r for r in changes if r.is_replaced]
    problems = []
    for r in replaced:
        why = ", ".join(".".join(str(x) for x in p) for p in r.replace_paths) or "a force-new attribute changed"
        problems.append(f"{r.address} would be REPLACED (forced by: {why})")
    suggestions = []
    unmatched_created = list(created)
    for d in deleted:
        twin = next((c for c in unmatched_created if c.type == d.type and strip_index(c.address).endswith("." + d.type + "." + c.name) or
                     (c.type == d.type and c.index == d.index)), None)
        if twin:
            unmatched_created.remove(twin)
            from_addr, to_addr = strip_index(d.address), strip_index(twin.address)
            if twin.index is not None and d.index is None:
                to_addr = twin.address
            suggestions.append(f"moved {{ from = {from_addr}  to = {to_addr} }}")
            problems.append(f"{twin.address} would be CREATED")
        problems.append(f"{d.address} would be DESTROYED")
    for c in unmatched_created:
        problems.append(f"{c.address} would be CREATED")
    if problems:
        msg = f"{len(deleted)} destroy, {len(created)} create, {len(replaced)} replace against the deployed dev state:\n  " + "\n  ".join(problems[:12])
        if len(problems) > 12:
            msg += f"\n  ... and {len(problems) - 12} more"
        if suggestions:
            msg += "\nSuggested moved blocks:\n  " + "\n  ".join(dict.fromkeys(suggestions))
        require(False, msg)


@requirement("R6.9", "prod is the same architecture with its own values",
             hint="envs/prod calls the same modules; only terraform.tfvars differs (project, environment, non-overlapping CIDRs).")
def prod_mirrors_dev(plan):
    prod = plan.others["prod"]
    dev_calls = {n: c.get("source") for n, c in _module_calls(plan).items()}
    require(dev_calls, "envs/dev calls no modules yet")
    prod_calls = {n: c.get("source") for n, c in _module_calls(prod).items()}
    require(dev_calls == prod_calls, f"Module calls differ: dev {sorted(dev_calls.items())} vs prod {sorted(prod_calls.items())}")
    require(plan.type_counts() == prod.type_counts(), "dev and prod would build different sets of resources")
    require(plan.variable_value("project_id") != prod.variable_value("project_id"), "prod must use its own project_id")
    require(prod.variable_value("environment") == "prod", "prod's environment variable should be \"prod\"")
    nets = []
    for env, p in (("dev", plan), ("prod", prod)):
        for s in p.resources("google_compute_subnetwork"):
            if s.get("ip_cidr_range"):
                nets.append((env, s.get("name"), ipaddress.ip_network(s.get("ip_cidr_range"), strict=False)))
    for (e1, n1, a), (e2, n2, b) in itertools.combinations(nets, 2):
        if e1 != e2:
            require(not a.overlaps(b), f"{e1} subnet {n1} ({a}) overlaps {e2} subnet {n2} ({b}) - they could never be peered")


@requirement("R6.10", "Firewall rules are data-driven and the lesson 05 matrix still holds",
             hint="One google_compute_firewall with for_each over a map of rule objects; keep the same three rules.")
def firewall_map(plan):
    rules = plan.resources("google_compute_firewall")
    require(rules, "No firewall rules found")
    require(all(isinstance(r.index, str) for r in rules), "Firewall rules should come from one resource using for_each over a map")
    require(len({strip_index(r.address) for r in rules}) == 1, "All firewall rules should come from a single for_each resource")
    fw = Firewall(plan)
    web = plan.by_tag("web")
    app = plan.by_tag("app")
    require(len(web) == 1 and len(app) == 1, "Expected one VM tagged web and one tagged app")
    web, app = fw.instance(web[0], "web VM"), fw.instance(app[0], "app VM")
    matrix = [
        (fw.internet(), web, 80, True),
        (fw.internet(), web, 22, False),
        (fw.iap(), web, 22, True),
        (fw.iap(), app, 22, True),
        (web, app, 8080, True),
        (web, app, 22, False),
        (fw.internet(), app, 8080, False),
    ]
    for src, dst, port, want in matrix:
        v = fw.evaluate(src, dst, "tcp", port)
        require(v.allowed == want, f"{src.label} -> {dst.label}:{port} should be {'ALLOWED' if want else 'DENIED'} ({v.reason})")


# ------------------------------------------------------------------ challenge
@requirement("C6.1", "The VM module validates its machine_type",
             hint="validation block on modules/vm-service variable machine_type; tests/challenge must pass.", level="challenge")
def module_validation(plan):
    vm_mods = [mod for _, src, mod in _walk_module_configs(plan.configuration.get("root_module", {}))
               if "machine_type" in mod.get("variables", {})]
    require(vm_mods, "No module declares a machine_type variable")


@requirement("C6.2", "Every child module declares its provider requirements",
             hint='modules/<m>/versions.tf: terraform { required_providers { google = { source = "hashicorp/google", version = ">= 8.0, < 9.0" } } }',
             level="challenge")
def module_versions(plan):
    mods = plan.source.dirs("modules")
    require(mods, "No modules/ directory found")
    for m in mods:
        ok = False
        for tf_block in plan.source.blocks("terraform", under=f"modules/{m}", recursive=False):
            rp = tf_block.block("required_providers")
            if rp and "hashicorp/google" in rp.body and "version" in rp.body:
                ok = True
        require(ok, f"modules/{m} has no terraform {{ required_providers {{ google = {{ source, version }} }} }} block")


@requirement("C6.3", "Production VMs have deletion protection; dev VMs don't",
             hint="vm-service variable deletion_protection (default false); prod terraform.tfvars sets it to true.", level="challenge")
def deletion_protection(plan):
    for vm in plan.others["prod"].resources("google_compute_instance"):
        require(vm.get("deletion_protection") is True, f"prod {vm.get('name')} has no deletion protection")
    for vm in plan.resources("google_compute_instance"):
        require(vm.get("deletion_protection") is not True, f"dev {vm.get('name')} should stay easy to recreate (deletion_protection off)")


@requirement("C6.4", "Environment sizing comes from tfvars: prod web is e2-small, dev stays e2-micro",
             hint="Expose web_machine_type in envs/*/variables.tf, pass it to the module, set it in prod's tfvars.", level="challenge")
def sizing(plan):
    def web_type(p):
        vms = p.by_tag("web")
        require(len(vms) == 1, f"{p.name}: expected one web VM")
        return vms[0].get("machine_type")
    require(web_type(plan.others["prod"]) == "e2-small", f"prod web VM is {web_type(plan.others['prod'])}, expected e2-small")
    require(web_type(plan) == "e2-micro", f"dev web VM is {web_type(plan)}, expected e2-micro (changing it would update the deployed VM)")
