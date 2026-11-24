"""Fabricate a Terraform state file that looks like a configuration was applied.

Authors use this to ship "already deployed" environments for state lessons
(refactoring with `moved` blocks, `terraform state` drills, drift simulation)
without ever touching Google Cloud:

    python -m coursekit.statefab <config_dir> <out.tfstate> [root]

`root` is the root module inside the tree (e.g. envs/dev) when the tree uses
local modules such as ../../modules/network.

How it works:
  1. plan the configuration offline (fake token, local backend);
  2. turn every planned resource into a state instance, filling values that are
     "known after apply" with schema-typed fakes (strings, 0, false, [], {});
  3. re-plan against that state and fold any known planned values back in,
     repeating until the plan has no creates, deletes or replacements
     (references such as subnet.network then agree with the fake IDs).
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from . import terraform as tf
from .cloudsim import _balanced

STATE_NAME = "course.tfstate"


def _schemas(build: Path) -> dict[str, Any]:
    res = tf.run(["providers", "schema", "-json"], cwd=build)
    data = json.loads(res.stdout)
    out: dict[str, Any] = {}
    for provider in data.get("provider_schemas", {}).values():
        out.update(provider.get("resource_schemas", {}))
    return out


def _fake_for(ctype: Any, hint: str) -> Any:
    if ctype == "string":
        return f"fake-{hint}"
    if ctype == "number":
        return 0
    if ctype == "bool":
        return False
    if isinstance(ctype, list):
        kind = ctype[0]
        if kind in ("list", "set"):
            return []
        if kind == "map":
            return {}
        if kind == "object":
            return {k: _fake_for(t, f"{hint}-{k}") for k, t in ctype[1].items()}
    return None


# Realistic IDs: providers validate formats when an ID is passed to another
# resource (e.g. a peering's `network`), so "fake-..." strings are not enough.
_ID_TEMPLATES = {
    "google_compute_network": "projects/{project}/global/networks/{name}",
    "google_compute_subnetwork": "projects/{project}/regions/{region}/subnetworks/{name}",
    "google_compute_firewall": "projects/{project}/global/firewalls/{name}",
    "google_compute_instance": "projects/{project}/zones/{zone}/instances/{name}",
    "google_compute_router": "projects/{project}/regions/{region}/routers/{name}",
    "google_compute_router_nat": "{project}/{region}/{router}/{name}",
    "google_compute_address": "projects/{project}/regions/{region}/addresses/{name}",
    "google_compute_global_address": "projects/{project}/global/addresses/{name}",
    "google_compute_global_forwarding_rule": "projects/{project}/global/forwardingRules/{name}",
    "google_compute_network_peering": "{network_name}/{name}",
    "google_compute_instance_template": "projects/{project}/global/instanceTemplates/{name}",
    "google_compute_health_check": "projects/{project}/global/healthChecks/{name}",
    "google_compute_backend_service": "projects/{project}/global/backendServices/{name}",
    "google_service_account": "projects/{project}/serviceAccounts/{email}",
    "google_storage_bucket": "{name}",
    "google_project_service": "{project}/{service}",
    "google_project_iam_member": "{project}/{role}/{member}",
}
_SELF_LINK_PREFIX = "https://www.googleapis.com/compute/v1/"

# Other computed attributes that providers validate when passed to another resource.
_ATTR_TEMPLATES = {
    ("google_service_account", "name"): "projects/{project}/serviceAccounts/{email}",
    ("google_service_account", "member"): "serviceAccount:{email}",
    ("google_service_account", "unique_id"): "100000000000000000001",
    ("google_project_iam_custom_role", "name"): "projects/{project}/roles/{role_id}",
    ("google_iam_workload_identity_pool", "name"): "projects/123456789012/locations/global/workloadIdentityPools/{workload_identity_pool_id}",
    ("google_service_account_key", "name"): "projects/{project}/serviceAccounts/sa@{project}.iam.gserviceaccount.com/keys/0123456789abcdef",
    ("google_logging_project_sink", "writer_identity"): "serviceAccount:service-123456789012@gcp-sa-logging.iam.gserviceaccount.com",
    ("google_monitoring_notification_channel", "name"): "projects/{project}/notificationChannels/1234567890123456789",
}


def _realistic_id(rtype: str, after: dict[str, Any], project: str) -> str | None:
    template = _ID_TEMPLATES.get(rtype)
    if not template:
        return None
    ctx = {k: v for k, v in after.items() if isinstance(v, str)}
    ctx.setdefault("project", project)
    ctx.setdefault("name", ctx.get("account_id", "resource"))
    ctx.setdefault("region", "us-central1")
    ctx.setdefault("zone", "us-central1-a")
    ctx.setdefault("email", f"{ctx.get('account_id', 'sa')}@{project}.iam.gserviceaccount.com")
    ctx["network_name"] = str(ctx.get("network", "network")).rsplit("/", 1)[-1]
    try:
        return template.format(**ctx)
    except KeyError:
        return None


def _apply_realistic_ids(rtype: str, attrs: dict[str, Any], unknown: dict[str, Any], project: str) -> dict[str, Any]:
    if unknown.get("project") is True:
        attrs["project"] = project
    rid = _realistic_id(rtype, attrs, project)
    if rid and unknown.get("id") is True:
        attrs["id"] = rid
    if rid and unknown.get("self_link") is True and rtype.startswith("google_compute_"):
        attrs["self_link"] = _SELF_LINK_PREFIX + rid
    ctx = {k: v for k, v in attrs.items() if isinstance(v, str)}
    ctx.setdefault("project", project)
    ctx.setdefault("email", f"{ctx.get('account_id', 'sa')}@{project}.iam.gserviceaccount.com")
    for (t, attr), template in _ATTR_TEMPLATES.items():
        if t == rtype and unknown.get(attr) is True:
            try:
                attrs[attr] = template.format(**ctx)
            except KeyError:
                pass
    return attrs


_PROJECT = {"value": "fake-project"}   # set per fabricate() run


def _fill(after: Any, unknown: Any, block: dict[str, Any], hint: str) -> Any:
    """Replace unknown markers in `after` using the resource block schema."""
    if not isinstance(after, dict):
        after = {}
    out = dict(after)
    attrs = block.get("attributes", {})
    unknown = unknown if isinstance(unknown, dict) else {}
    for name, spec in attrs.items():
        if unknown.get(name) is True:
            if spec.get("type") == "string" and (name == "project" or name.endswith("_project")):
                out[name] = _PROJECT["value"]   # providers cross-check these against self_links
            else:
                out[name] = _fake_for(spec.get("type"), f"{hint}-{name}")
        elif name not in out:
            out[name] = None
    for name, nested in block.get("block_types", {}).items():
        val = out.get(name)
        unk = unknown.get(name)
        if isinstance(val, list):
            unk_list = unk if isinstance(unk, list) else []
            out[name] = [
                _fill(v, unk_list[i] if i < len(unk_list) else {}, nested.get("block", {}), f"{hint}-{name}")
                for i, v in enumerate(val)
            ]
        elif val is None:
            out[name] = [] if nested.get("nesting_mode") in ("list", "set") else None
    return out


def _merge_known(state_attrs: dict[str, Any], after: Any, unknown: Any) -> dict[str, Any]:
    if not isinstance(after, dict):
        return state_attrs
    unknown = unknown if isinstance(unknown, dict) else {}
    merged = dict(state_attrs)
    for k, v in after.items():
        u = unknown.get(k)
        if u is True:
            continue
        if isinstance(v, list) and isinstance(merged.get(k), list) and isinstance(u, list):
            merged[k] = [
                _merge_known(merged[k][i], item, u[i] if i < len(u) else {})
                if i < len(merged[k]) and isinstance(item, dict) and isinstance(merged[k][i], dict)
                else item
                for i, item in enumerate(v)
            ]
        else:
            merged[k] = v
    return merged


def _sensitive_paths(marks: Any, path: list[dict[str, Any]] | None = None) -> list[list[dict[str, Any]]]:
    """Convert plan `after_sensitive` markers into state `sensitive_attributes` paths."""
    path = path or []
    out: list[list[dict[str, Any]]] = []
    if marks is True:
        return [path]
    if isinstance(marks, dict):
        for k, v in marks.items():
            out += _sensitive_paths(v, path + [{"type": "get_attr", "value": k}])
    elif isinstance(marks, list):
        for i, v in enumerate(marks):
            out += _sensitive_paths(v, path + [{"type": "index", "value": {"value": i, "type": "number"}}])
    return out


def _cty_type(value: Any) -> Any:
    """Infer the state's type annotation for an output value."""
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return ["object", {k: _cty_type(v) for k, v in value.items()}]
    if isinstance(value, list):
        return ["tuple", [_cty_type(v) for v in value]]
    return "dynamic"


def _outputs_from(plan: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for name, change in (plan.get("output_changes") or {}).items():
        after = change.get("after")
        if change.get("after_unknown") or after is None:
            continue
        entry = {"value": after, "type": _cty_type(after)}
        if change.get("after_sensitive") is True:
            entry["sensitive"] = True
        out[name] = entry
    return out


def _plan(build: Path) -> dict[str, Any]:
    res = tf.run(["plan", "-input=false", "-refresh=false", "-lock=false", "-no-color", "-out=fab.tfplan"], cwd=build)
    if not res.ok:
        raise SystemExit("plan failed:\n" + res.output)
    return json.loads(tf.run(["show", "-json", "fab.tfplan"], cwd=build).stdout)


def _instance_key(rc: dict[str, Any]) -> tuple[str, str, str, str, Any]:
    return (rc.get("module_address", ""), rc.get("mode", "managed"), rc["type"], rc["name"], rc.get("index"))


def fabricate(config_dir: Path, out: Path, max_rounds: int = 6, root: str = "") -> dict[str, int]:
    tmp = Path(tempfile.mkdtemp(prefix="statefab-"))
    build = tmp / root if root else tmp
    try:
        tf.sync_build_dir(config_dir, tmp, roots=[root])
        # Intermediate rounds replace resources whose fake IDs don't line up yet; prevent_destroy
        # would abort those plans. Lifecycle settings don't end up in state, so drop them here.
        # import blocks would call the API; the fabricated state is the post-import state anyway.
        for f in tmp.rglob("*.tf"):
            text = f.read_text(encoding="utf-8")
            new = re.sub(r"prevent_destroy\s*=\s*true", "prevent_destroy = false", text)
            for m in reversed(list(re.finditer(r"(?m)^import\s*\{", new))):
                block = _balanced(new, m.end() - 1)
                new = new[:m.start()] + new[m.end() - 1 + len(block):]
            if new != text:
                f.write_text(new, encoding="utf-8")
        init =tf.run(["init", "-input=false", "-no-color"], cwd=build)
        if not init.ok:
            raise SystemExit(init.output)
        schemas = _schemas(build)
        plan = _plan(build)
        tf_version = plan.get("terraform_version", "1.9.0")

        project = (plan.get("variables", {}).get("project_id", {}) or {}).get("value") or tf.DEFAULT_PROJECT
        _PROJECT["value"] = project

        schema_versions: dict[str, int] = {}

        def walk(mod: dict[str, Any]) -> None:
            for r in mod.get("resources", []):
                schema_versions[r["address"]] = r.get("schema_version", 0)
            for child in mod.get("child_modules", []):
                walk(child)

        walk(plan.get("planned_values", {}).get("root_module", {}))

        outputs: dict[str, Any] = {}
        instances: dict[tuple, dict[str, Any]] = {}
        for rc in plan.get("resource_changes", []):
            if rc.get("mode") != "managed":
                continue
            change = rc["change"]
            block = schemas.get(rc["type"], {}).get("block", {})
            hint = f"{rc['type'].removeprefix('google_')}-{rc['name']}" + (f"-{rc['index']}" if rc.get("index") is not None else "")
            attrs = _fill(change.get("after") or {}, change.get("after_unknown") or {}, block, hint)
            attrs = _apply_realistic_ids(rc["type"], attrs, change.get("after_unknown") or {}, project)
            instances[_instance_key(rc)] = {
                "rc": rc,
                "schema_version": schema_versions.get(rc["address"], 0),
                "attributes": attrs,
                "sensitive": _sensitive_paths(change.get("after_sensitive")),
            }

        def write() -> None:
            grouped: dict[tuple, dict[str, Any]] = {}
            for (module, mode, rtype, name, index), inst in instances.items():
                key = (module, mode, rtype, name)
                provider = inst["rc"].get("provider_name", "registry.terraform.io/hashicorp/google")
                res = grouped.setdefault(
                    key,
                    {
                        **({"module": module} if module else {}),
                        "mode": mode,
                        "type": rtype,
                        "name": name,
                        "provider": f'provider["{provider}"]',
                        "instances": [],
                    },
                )
                entry = {"schema_version": inst["schema_version"], "attributes": inst["attributes"], "sensitive_attributes": inst["sensitive"]}
                if index is not None:
                    entry = {"index_key": index, **entry}
                res["instances"].append(entry)
            state = {
                "version": 4,
                "terraform_version": tf_version,
                "serial": 1,
                "lineage": str(uuid.uuid5(uuid.NAMESPACE_URL, str(out.name))),
                "outputs": outputs,
                "resources": list(grouped.values()),
                "check_results": None,
            }
            (build / STATE_NAME).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8", newline="\n")

        stats = {}
        for round_ in range(1, max_rounds + 1):
            write()
            plan = _plan(build)
            stats = {"create": 0, "delete": 0, "update": 0, "replace": 0}
            for rc in plan.get("resource_changes", []):
                acts = rc["change"]["actions"]
                if acts == ["no-op"] or rc.get("mode") != "managed":
                    continue
                if "delete" in acts and "create" in acts:
                    stats["replace"] += 1
                elif acts == ["create"]:
                    stats["create"] += 1
                elif acts == ["delete"]:
                    stats["delete"] += 1
                else:
                    stats["update"] += 1
                key = _instance_key(rc)
                if key in instances:
                    instances[key]["attributes"] = _merge_known(
                        instances[key]["attributes"], rc["change"].get("after"), rc["change"].get("after_unknown")
                    )
            new_outputs = _outputs_from(plan)
            outputs_changed = new_outputs != outputs
            outputs.clear()
            outputs.update(new_outputs)
            print(f"round {round_}: {stats}" + (" (outputs updated)" if outputs_changed else ""), file=sys.stderr)
            if not any(stats.values()) and not outputs_changed:
                break
        write()
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(build / STATE_NAME, out)
        return stats
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        raise SystemExit("usage: python -m coursekit.statefab <config_dir> <out.tfstate> [root]")
    result = fabricate(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(),
                       root=sys.argv[3] if len(sys.argv) == 4 else "")
    print(json.dumps(result))
