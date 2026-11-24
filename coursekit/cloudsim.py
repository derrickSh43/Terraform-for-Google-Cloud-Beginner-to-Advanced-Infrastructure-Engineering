"""Offline simulation of `import` blocks.

A real `import` block makes Terraform read the object from the cloud API, which fails with the
course's fake token. Terraform skips an import whose target address is already in state, so the
course plays the cloud's part: a lesson ships an inventory of objects that exist in the cloud but
are not in state (`"cloud": {"dev": "state/dev.cloud.json"}` in lesson.json). Before planning, each
import block in a root is resolved against that inventory:

  * found      -> the object is written into the prepared state at the `to` address, exactly what a
                  real import does; the plan then shows whether the configuration matches it.
  * not found  -> the plan fails like a real one would ("Cannot import non-existent remote object").

Supported expressions: literal `id`/`to`, and `for_each` over a literal list/set/map or a local,
with `each.key` / `each.value` interpolation in `id` and `to`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROVIDER = 'provider["registry.terraform.io/hashicorp/google"]'


class ImportFailed(Exception):
    pass


@dataclass
class Imported:
    address: str
    id: str
    type: str


# ------------------------------------------------------------------ tiny HCL value reader
def _balanced(text: str, start: int) -> str:
    """Return the expression starting at `start`, spanning brackets/braces/parens across lines."""
    depth, i, in_str = 0, start, False
    while i < len(text):
        c = text[i]
        if in_str:
            if c == "\\":
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c in "[{(":
            depth += 1
        elif c in "]})":
            depth -= 1
        elif c == "\n" and depth == 0:
            break
        i += 1
    return text[start:i].strip()


def _attr_expr(body: str, name: str) -> str | None:
    m = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*", body)
    return _balanced(body, m.end()) if m else None


def _literal(expr: str, locals_: dict[str, str]) -> Any:
    expr = expr.strip()
    m = re.fullmatch(r"(?:toset|tolist|tomap)\((.*)\)", expr, re.S)
    if m:
        return _literal(m.group(1), locals_)
    m = re.fullmatch(r"local\.([A-Za-z0-9_-]+)", expr)
    if m:
        if m.group(1) not in locals_:
            raise ImportFailed(f"for_each refers to local.{m.group(1)}, which isn't defined in this root module")
        return _literal(locals_[m.group(1)], locals_)
    if expr.startswith("["):
        items = re.findall(r'"([^"]*)"', expr)
        return {i: i for i in items}
    if expr.startswith("{"):
        pairs = re.findall(r'"?([A-Za-z0-9_.-]+)"?\s*[=:]\s*"([^"]*)"', expr)
        if pairs:
            return dict(pairs)
    raise ImportFailed(
        f"The offline import simulator can't evaluate for_each = {expr!r}. "
        "Use a literal list/set/map, or a local that holds one.")


def _locals(root_text: str) -> dict[str, str]:
    out = {}
    for m in re.finditer(r"(?m)^locals\s*\{", root_text):
        body = _balanced(root_text, m.end() - 1)[1:-1]
        for a in re.finditer(r"(?m)^\s{2}([A-Za-z0-9_-]+)\s*=\s*", body):
            out[a.group(1)] = _balanced(body, a.end())
    return out


def _subst(expr: str, key: str | None, value: str | None) -> str:
    expr = expr.strip()
    if expr == "each.key" and key is not None:
        return key
    if expr == "each.value" and value is not None:
        return value
    if expr.startswith('"') and expr.endswith('"'):
        expr = expr[1:-1]
    if key is not None:
        expr = expr.replace("${each.key}", key).replace("each.key", f'"{key}"')
        expr = expr.replace("${each.value}", value or "").replace("each.value", f'"{value}"')
    if "${" in expr or "var." in expr or "local." in expr:
        raise ImportFailed(f"The offline import simulator can't evaluate {expr!r}: use literals or each.key/each.value")
    return expr


def import_blocks(root_dir: Path) -> list[tuple[str, str, str]]:
    """(to, id, file) for every import block in a root module (expanding for_each)."""
    texts = {p.name: p.read_text(encoding="utf-8", errors="replace")
             for p in sorted(root_dir.glob("*.tf")) if not p.name.startswith("zz_course_")}
    all_text = "\n".join(re.sub(r"(?m)(#|//).*$", "", t) for t in texts.values())
    locals_ = _locals(all_text)
    out = []
    for fname, text in texts.items():
        clean = re.sub(r"(?m)^\s*(#|//).*$", "", text)
        for m in re.finditer(r"(?m)^import\s*\{", clean):
            body = _balanced(clean, m.end() - 1)[1:-1]
            to, rid = _attr_expr(body, "to"), _attr_expr(body, "id")
            if not to or not rid:
                continue  # terraform validate reports this
            fe = _attr_expr(body, "for_each")
            if fe:
                for k, v in _literal(fe, locals_).items():
                    out.append((_subst(to, k, v), _subst(rid, k, v), fname))
            else:
                out.append((_subst(to, None, None), _subst(rid, None, None), fname))
    return out


# ------------------------------------------------------------------ addresses and state
_ADDR = re.compile(r'^((?:module\.[A-Za-z0-9_-]+(?:\["[^"]*"\]|\[\d+\])?\.)*)([a-z0-9_]+)\.([A-Za-z0-9_-]+)(\["[^"]*"\]|\[\d+\])?$')


def parse_address(addr: str) -> tuple[str, str, str, Any]:
    m = _ADDR.match(addr.replace(" ", ""))
    if not m:
        raise ImportFailed(f"Can't read the import target address {addr!r}")
    module, rtype, name, idx = m.group(1).rstrip("."), m.group(2), m.group(3), m.group(4)
    key: Any = None
    if idx:
        inner = idx[1:-1]
        key = json.loads(inner) if inner.startswith('"') else int(inner)
    return module, rtype, name, key


def _norm(addr: str) -> str:
    module, rtype, name, key = parse_address(addr)
    idx = "" if key is None else (f'["{key}"]' if isinstance(key, str) else f"[{key}]")
    return (module + "." if module else "") + f"{rtype}.{name}{idx}"


def _state_addresses(state: dict[str, Any]) -> set[str]:
    out = set()
    for r in state.get("resources", []):
        if r.get("mode") != "managed":
            continue
        base = (r["module"] + "." if r.get("module") else "") + f"{r['type']}.{r['name']}"
        for inst in r.get("instances", []):
            k = inst.get("index_key")
            out.add(base + ("" if k is None else (f'["{k}"]' if isinstance(k, str) else f"[{k}]")))
    return out


def load_inventory(path: Path | None) -> list[dict[str, Any]]:
    if not path or not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("objects", [])


def apply(root_dir: Path, inventory: list[dict[str, Any]]) -> list[Imported]:
    """Resolve the root's import blocks against the inventory and write them into course.tfstate."""
    blocks = import_blocks(root_dir)
    if not blocks:
        return []
    state_file = root_dir / "course.tfstate"
    if state_file.exists():
        state = json.loads(state_file.read_text(encoding="utf-8"))
    else:
        state = {"version": 4, "terraform_version": "1.9.0", "serial": 1,
                 "lineage": "c0c0c0c0-0000-4000-8000-000000000020", "outputs": {}, "resources": [], "check_results": None}
    existing = _state_addresses(state)
    done: list[Imported] = []
    for to, rid, fname in blocks:
        module, rtype, name, key = parse_address(to)
        addr = _norm(to)
        if addr in existing:
            continue  # Terraform skips imports into addresses it already manages
        matches = [o for o in inventory if rid == o["id"] or rid in o.get("aliases", [])]
        if not matches:
            raise ImportFailed(
                f"Error: Cannot import non-existent remote object\n\n  on {fname}: import of {to} with id {rid!r}\n\n"
                f"No object with that ID exists in the (simulated) project. Check the ID format and name.")
        obj = matches[0]
        if obj["type"] != rtype:
            raise ImportFailed(
                f"Error: import {to}: id {rid!r} is a {obj['type']}, but the target is a {rtype}")
        entry = next((r for r in state["resources"] if r.get("mode") == "managed" and r["type"] == rtype
                      and r["name"] == name and r.get("module", "") == module), None)
        if entry is None:
            entry = {"mode": "managed", "type": rtype, "name": name, "provider": PROVIDER, "instances": []}
            if module:
                entry["module"] = module
            state["resources"].append(entry)
        inst = {"schema_version": obj.get("schema_version", 0), "attributes": obj["attributes"],
                "sensitive_attributes": obj.get("sensitive_attributes", [])}
        if key is not None:
            inst["index_key"] = key
        entry["instances"].append(inst)
        existing.add(addr)
        done.append(Imported(addr, rid, rtype))
    state["serial"] = int(state.get("serial", 1)) + 1
    with open(state_file, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(state, fh, indent=2)
    return done


def build_inventory(state_file: Path, picks: dict[str, list[str]], out: Path) -> None:
    """Author helper: copy resources (by address) out of a fabricated state into an inventory file.

    `picks` maps a state address to the import IDs it answers to (first = canonical id).
    """
    state = json.loads(state_file.read_text(encoding="utf-8"))
    objs = []
    for r in state["resources"]:
        base = (r["module"] + "." if r.get("module") else "") + f"{r['type']}.{r['name']}"
        for inst in r["instances"]:
            k = inst.get("index_key")
            addr = base + ("" if k is None else (f'["{k}"]' if isinstance(k, str) else f"[{k}]"))
            if addr in picks:
                ids = picks[addr]
                objs.append({"type": r["type"], "id": ids[0], "aliases": ids[1:],
                             "schema_version": inst.get("schema_version", 0),
                             "attributes": inst["attributes"],
                             "sensitive_attributes": inst.get("sensitive_attributes", [])})
    missing = set(picks) - {a for a in picks if any(o["id"] == picks[a][0] for o in objs)}
    if missing:
        raise SystemExit(f"not in state: {sorted(missing)}")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"comment": "Objects that exist in the cloud but not in Terraform state (created by hand).",
                   "objects": objs}, fh, indent=2)
