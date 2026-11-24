"""A friendly read-only model over `terraform show -json <planfile>`.

Validators should ask questions about *what would be built*, not about how the
student spelled it. Prefer:

    plan.resources("google_compute_instance")      # by type, any name, any module
    res.get("boot_disk.0.initialize_params.0.image")
    res.references_type("google_service_account")  # wiring between resources

over hard-coding addresses, so that multiple correct solutions pass.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_MISSING = object()
_INDEX_RE = re.compile(r"\[[^\]]*\]")


def _walk(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split(".") if path else []:
        if isinstance(cur, list):
            if not part.isdigit() or int(part) >= len(cur):
                return _MISSING
            cur = cur[int(part)]
        elif isinstance(cur, dict):
            if part not in cur:
                return _MISSING
            cur = cur[part]
        else:
            return _MISSING
    return cur


def _collect_refs(expr: Any, out: list[str]) -> None:
    if isinstance(expr, dict):
        refs = expr.get("references")
        if isinstance(refs, list):
            out.extend(r for r in refs if isinstance(r, str))
        for k, v in expr.items():
            if k != "references":
                _collect_refs(v, out)
    elif isinstance(expr, list):
        for v in expr:
            _collect_refs(v, out)


def strip_index(address: str) -> str:
    return _INDEX_RE.sub("", address)


@dataclass
class Resource:
    address: str
    type: str
    name: str
    mode: str
    module: str                     # "" for root, else "module.a.module.b"
    index: Any
    actions: list[str]
    after: dict[str, Any]
    unknown: dict[str, Any]
    config: dict[str, Any] = field(default_factory=dict)
    previous_address: str | None = None
    replace_paths: list[Any] = field(default_factory=list)

    @property
    def is_replaced(self) -> bool:
        return "delete" in self.actions and "create" in self.actions

    # ---- values ---------------------------------------------------------
    def get(self, path: str, default: Any = None) -> Any:
        """Planned value at a dotted path (lists use numeric parts)."""
        v = _walk(self.after, path)
        return default if v is _MISSING or v is None else v

    def has(self, path: str) -> bool:
        return _walk(self.after, path) not in (_MISSING, None) or self.is_unknown(path)

    def is_unknown(self, path: str) -> bool:
        """True when the value is only known after apply (e.g. generated IDs)."""
        return _walk(self.unknown, path) is True

    def blocks(self, path: str) -> list[dict[str, Any]]:
        v = self.get(path, [])
        return v if isinstance(v, list) else []

    # ---- configuration --------------------------------------------------
    @property
    def expressions(self) -> dict[str, Any]:
        return self.config.get("expressions", {})

    def references(self, path: str = "") -> list[str]:
        """All references used in the expressions under `path` ("" = whole block).

        Path parts skip block list indexes, e.g. "network_interface.subnetwork".
        """
        node: Any = self.expressions
        for part in path.split(".") if path else []:
            if part.isdigit():          # value paths may carry list indexes; expressions don't need them
                continue
            if isinstance(node, list):
                node = [n.get(part) for n in node if isinstance(n, dict) and part in n]
                if len(node) == 1:
                    node = node[0]
            elif isinstance(node, dict):
                node = node.get(part)
            if node is None:
                return []
        refs: list[str] = []
        _collect_refs(node, refs)
        return refs

    def references_type(self, rtype: str, path: str = "") -> bool:
        return any(r.split(".", 1)[0] == rtype or r.startswith(f"{rtype}.") for r in self.references(path))

    def references_address(self, address: str, path: str = "") -> bool:
        base = strip_index(address)
        return any(strip_index(r) == base or strip_index(r).startswith(base + ".") for r in self.references(path))

    def constant(self, path: str) -> Any:
        node = _walk(self.expressions, path)
        if isinstance(node, dict) and "constant_value" in node:
            return node["constant_value"]
        return None

    @property
    def depends_on(self) -> list[str]:
        return list(self.config.get("depends_on", []))

    def depends_on_type(self, rtype: str) -> bool:
        return any(d.startswith(rtype + ".") for d in self.depends_on) or self.references_type(rtype)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Resource {self.address}>"


class Plan:
    def __init__(self, data: dict[str, Any], *, name: str = "main", source: Any = None, root: str = ""):
        self.data = data
        self.name = name
        self.root = root              # root module dir inside the student's tree
        self.source = source          # coursekit.hcl.Source for the whole tree (may be None)
        self.others: dict[str, "Plan"] = {}   # sibling roots, e.g. plan.others["prod"]
        self.imported: dict[str, str] = {}    # address -> import id (resolved by coursekit.cloudsim)
        self.configuration = data.get("configuration", {})
        self._resources = self._build_resources()

    # ---- construction ---------------------------------------------------
    def _module_config(self, module: str) -> dict[str, Any]:
        node = self.configuration.get("root_module", {})
        if not module:
            return node
        for name in re.findall(r"module\.([^.\[]+)", module):
            node = node.get("module_calls", {}).get(name, {}).get("module", {})
        return node

    def _config_for(self, module: str, mode: str, rtype: str, name: str) -> dict[str, Any]:
        prefix = "data." if mode == "data" else ""
        want = f"{prefix}{rtype}.{name}"
        for r in self._module_config(module).get("resources", []):
            if r.get("address") == want:
                return r
        return {}

    def _build_resources(self) -> list[Resource]:
        out = []
        for rc in self.data.get("resource_changes", []):
            change = rc.get("change", {})
            module = rc.get("module_address", "")
            out.append(
                Resource(
                    address=rc["address"],
                    type=rc["type"],
                    name=rc["name"],
                    mode=rc.get("mode", "managed"),
                    module=module,
                    index=rc.get("index"),
                    actions=change.get("actions", []),
                    after=change.get("after") or {},
                    unknown=change.get("after_unknown") or {},
                    config=self._config_for(module, rc.get("mode", "managed"), rc["type"], rc["name"]),
                    previous_address=rc.get("previous_address"),
                    replace_paths=rc.get("change", {}).get("replace_paths") or [],
                )
            )
        return out

    # ---- resources ------------------------------------------------------
    def resources(self, rtype: str | None = None, *, include_deleted: bool = False) -> list[Resource]:
        res = [r for r in self._resources if r.mode == "managed"]
        if not include_deleted:
            res = [r for r in res if r.actions != ["delete"]]
        if rtype:
            res = [r for r in res if r.type == rtype]
        return res

    def resource(self, address: str) -> Resource | None:
        for r in self._resources:
            if r.address == address:
                return r
        return None

    def before(self, address: str) -> dict[str, Any]:
        """Prior-state values of a resource change ({} for creates)."""
        for rc in self.data.get("resource_changes", []):
            if rc["address"] == address:
                return rc.get("change", {}).get("before") or {}
        return {}

    def changed_attributes(self, address: str) -> list[str]:
        """Top-level attributes whose value differs between prior state and plan (unknowns count as changed)."""
        for rc in self.data.get("resource_changes", []):
            if rc["address"] == address:
                ch = rc.get("change", {})
                b, a, u = ch.get("before") or {}, ch.get("after") or {}, ch.get("after_unknown") or {}
                return sorted(k for k in set(a) | set(b) if u.get(k) is True or (k in a and a.get(k) != b.get(k)))
        return []

    def check_results(self) -> list[dict[str, Any]]:
        """`check` block results: [{"address": "module.x.check.y", "status": "pass|fail|unknown", "messages": [...]}]."""
        out = []
        for c in self.data.get("checks", []) or []:
            if c.get("address", {}).get("kind") != "check":
                continue
            msgs = [p.get("message", "") for i in c.get("instances", []) or [] for p in i.get("problems", []) or []]
            out.append({"address": c["address"].get("to_display", ""), "status": c.get("status", "unknown"), "messages": msgs})
        return out

    def all_changes(self) -> list[Resource]:
        """Every managed resource change, including deletes and no-ops."""
        return [r for r in self._resources if r.mode == "managed"]

    def find_by_id(self, value: str) -> Resource | None:
        """Resolve a known ID / self_link string (e.g. from prepared state) to a resource."""
        if not isinstance(value, str) or not value:
            return None
        for r in self.resources():
            if value in (r.get("id"), r.get("self_link")):
                return r
        return None

    def type_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.resources():
            counts[r.type] = counts.get(r.type, 0) + 1
        return counts

    def types(self) -> set[str]:
        return {r.type for r in self.resources()}

    def by_tag(self, tag: str, rtype: str = "google_compute_instance") -> list[Resource]:
        return [r for r in self.resources(rtype) if tag in (r.get("tags") or [])]

    def find_by_address_ref(self, ref: str, module: str = "") -> list[Resource]:
        """Resolve a configuration reference like 'google_compute_network.vpc.id'.

        References are relative to the module they appear in, so pass the
        referring resource's module address ("" = root)."""
        m = re.match(r'^([a-z0-9_]+)\.([A-Za-z0-9_-]+)(\[[^\]]*\])?', ref)
        if not m or m.group(1) in ("module", "data", "var", "local", "each", "count", "path", "self"):
            return []
        base = f"{m.group(1)}.{m.group(2)}"
        if m.group(3):  # an indexed reference points at exactly one instance
            full = (module + "." if module else "") + base + m.group(3)
            exact = [r for r in self.resources() if r.address == full and r.module == module]
            if exact:
                return exact
        prefix = module + "." if module else ""
        return [r for r in self.resources() if r.module == module and strip_index(r.address) == strip_index(prefix + base)]

    def expand_ref(self, ref: str, module: str = "", depth: int = 0) -> list[tuple[str, str]]:
        """Follow a reference across module boundaries to resource references.

        `var.x` inside module M resolves through the expression the parent passes
        for x; `module.c.out` resolves through output `out` of child module c.
        Returns (resource_ref, module_address) pairs; unresolvable refs yield [].
        """
        if depth > 8:
            return []
        parts = ref.split(".")
        if parts[0] == "var":
            if not module or len(parts) < 2:
                return []
            var = re.sub(r"\[.*", "", parts[1])
            names = re.findall(r"module\.([^.\[]+)", module)
            parent = module.rsplit(".module.", 1)[0] if ".module." in module else ""
            call = self._module_config(parent).get("module_calls", {}).get(names[-1], {})
            refs: list[str] = []
            _collect_refs(call.get("expressions", {}).get(var, {}), refs)
            return [x for r in refs for x in self.expand_ref(r, parent, depth + 1)]
        if parts[0] == "module":
            if len(parts) < 3:
                return []
            child = (module + "." if module else "") + "module." + re.sub(r"\[.*", "", parts[1])
            output = re.sub(r"\[.*", "", parts[2])
            key = re.search(r"(\[[^\]]+\])", parts[2])   # module.network.subnet_ids["web"]
            refs = []
            _collect_refs(self._module_config(child).get("outputs", {}).get(output, {}).get("expression", {}), refs)
            out = [x for r in refs for x in self.expand_ref(r, child, depth + 1)]
            if key:
                # A map output built with `for k, s in resource : k => ...` - apply the key
                # to un-indexed for_each resources so only that instance matches.
                keyed = []
                for r, mod in out:
                    bits = r.split(".")
                    if len(bits) >= 2 and "[" not in bits[1]:
                        keyed.append((".".join([bits[0], bits[1] + key.group(1)] + bits[2:]), mod))
                    else:
                        keyed.append((r, mod))
                out = keyed
            return out
        if parts[0] in ("local", "each", "count", "path", "self", "terraform", "data"):
            return []
        return [(ref, module)]

    def module_input_resources(self, module: str, rtypes: tuple[str, ...]) -> list[Resource]:
        """Resources of the given types passed into module `module` through any input variable."""
        if not module:
            return []
        names = re.findall(r"module\.([^.\[]+)", module)
        parent = module.rsplit(".module.", 1)[0] if ".module." in module else ""
        call = self._module_config(parent).get("module_calls", {}).get(names[-1], {})
        found: dict[str, Resource] = {}
        for var in call.get("expressions", {}):
            for ref, mod in self.expand_ref(f"var.{var}", module):
                for r in self.find_by_address_ref(ref, mod):
                    if r.type in rtypes:
                        found[r.address] = r
        return list(found.values())

    def linked(self, res: Resource, rtype: str, path: str = "") -> list[Resource]:
        """Resources of `rtype` that `res` references, following module inputs/outputs."""
        pairs = [x for ref in res.references(path) for x in self.expand_ref(ref, res.module)]
        # Terraform lists `x.y["k"].id`, `x.y["k"]` and `x.y` together; when an
        # indexed form exists, the bare `x.y` must not widen the match to every instance.
        indexed = {(mod, ".".join(strip_index(r).split(".")[:2])) for r, mod in pairs if "[" in r}
        found: dict[str, Resource] = {}
        for ref, mod in pairs:
            if "[" not in ref and (mod, ".".join(ref.split(".")[:2])) in indexed:
                continue
            for r in self.find_by_address_ref(ref, mod):
                if r.type == rtype:
                    found[r.address] = r
        return list(found.values())

    # ---- configuration-level facts -------------------------------------
    def data_sources(self, rtype: str | None = None) -> list[dict[str, Any]]:
        out = []

        def visit(mod: dict[str, Any]) -> None:
            for r in mod.get("resources", []):
                if r.get("mode") == "data" and (rtype is None or r.get("type") == rtype):
                    out.append(r)
            for call in mod.get("module_calls", {}).values():
                visit(call.get("module", {}))

        visit(self.configuration.get("root_module", {}))
        return out

    def variables(self) -> dict[str, dict[str, Any]]:
        return self.configuration.get("root_module", {}).get("variables", {})

    def variable_value(self, name: str) -> Any:
        return self.data.get("variables", {}).get(name, {}).get("value")

    def outputs(self) -> dict[str, dict[str, Any]]:
        return self.configuration.get("root_module", {}).get("outputs", {})

    def output_references(self, name: str) -> list[str]:
        refs: list[str] = []
        _collect_refs(self.outputs().get(name, {}).get("expression", {}), refs)
        return refs

    def module_calls(self) -> dict[str, dict[str, Any]]:
        return self.configuration.get("root_module", {}).get("module_calls", {})

    def provider_config(self, name: str = "google") -> dict[str, Any]:
        return self.configuration.get("provider_config", {}).get(name, {})

    def provider_constraint(self, name: str = "google") -> str | None:
        return self.provider_config(name).get("version_constraint")

    def provider_references(self, name: str, arg: str) -> list[str]:
        refs: list[str] = []
        _collect_refs(self.provider_config(name).get("expressions", {}).get(arg, {}), refs)
        return refs

    def provider_constant(self, name: str, arg: str) -> Any:
        return self.provider_config(name).get("expressions", {}).get(arg, {}).get("constant_value")

