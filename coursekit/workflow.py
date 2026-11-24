"""Read GitHub Actions workflows without third-party packages.

A small YAML-subset parser that covers what workflow files use in practice:
block mappings and sequences (indented or not), `- key: value` items, block
scalars (`|`, `>`, with chomping indicators), quoted and plain scalars, flow
sequences `[a, b]` and flow mappings `{}`/`{a: b}`, and comments. Anchors,
aliases, tags and multi-document streams are not supported; workflows don't need them.

`on` is kept as the string "on" (YAML 1.1 would turn it into true).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


class YamlError(ValueError):
    pass


def _strip_comment(line: str) -> str:
    out, quote = [], None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _split_flow(s: str) -> list[str]:
    parts, depth, cur, quote = [], 0, [], None
    for ch in s:
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
            continue
        cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur).strip())
    return parts


def scalar(s: str) -> Any:
    s = s.strip()
    if s == "":
        return None
    if (s[0] == s[-1] == '"') or (s[0] == s[-1] == "'"):
        return s[1:-1]
    if s.startswith("[") and s.endswith("]"):
        return [scalar(p) for p in _split_flow(s[1:-1])]
    if s.startswith("{") and s.endswith("}"):
        out = {}
        for p in _split_flow(s[1:-1]):
            k, _, v = p.partition(":")
            out[scalar(k)] = scalar(v)
        return out
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    if s in ("null", "~"):
        return None
    return s


_KEY = re.compile(r'^(?P<key>"[^"]*"|\'[^\']*\'|[^:\s][^:]*?)\s*:(?:\s+(?P<val>.*))?$')


@dataclass
class _Line:
    indent: int
    text: str
    raw: str
    no: int


class _Parser:
    def __init__(self, text: str):
        self.raw = text.splitlines()
        self.lines: list[_Line] = []
        for no, raw in enumerate(self.raw):
            if raw.strip() in ("---", "..."):
                continue
            stripped = _strip_comment(raw)
            if stripped.strip():
                self.lines.append(_Line(len(stripped) - len(stripped.lstrip(" ")), stripped.strip(), raw, no))
        self.i = 0

    def parse(self) -> Any:
        if not self.lines:
            return {}
        return self.block(self.lines[0].indent)

    def block(self, indent: int) -> Any:
        if self.i < len(self.lines) and self.lines[self.i].text.startswith("- ") or (
                self.i < len(self.lines) and self.lines[self.i].text == "-"):
            return self.seq(indent)
        return self.mapping(indent)

    def block_scalar(self, header: str, parent_indent: int, start_no: int) -> str:
        folded = header.startswith(">")
        keep_trailing = "+" in header
        body, ind = [], None
        no = start_no + 1
        while no < len(self.raw):
            raw = self.raw[no]
            if raw.strip() == "":
                body.append("")
                no += 1
                continue
            cur = len(raw) - len(raw.lstrip(" "))
            if cur <= parent_indent:
                break
            ind = cur if ind is None else ind
            body.append(raw[ind:])
            no += 1
        while self.i < len(self.lines) and self.lines[self.i].no < no:
            self.i += 1
        text = (" " if folded else "\n").join(body)
        return text if keep_trailing else text.rstrip("\n") + ("" if "-" in header else "\n")

    def value_after(self, val: str | None, line: _Line) -> Any:
        if val is None or val == "":
            if self.i < len(self.lines):
                nxt = self.lines[self.i]
                if nxt.indent > line.indent or (nxt.indent == line.indent and nxt.text.startswith("-")):
                    return self.block(nxt.indent)
            return None
        if val[:1] in ("|", ">"):
            return self.block_scalar(val, line.indent, line.no)
        return scalar(val)

    def mapping(self, indent: int) -> dict:
        out: dict = {}
        while self.i < len(self.lines):
            line = self.lines[self.i]
            if line.indent < indent or line.text.startswith("- "):
                break
            if line.indent > indent:
                raise YamlError(f"line {line.no + 1}: unexpected indentation")
            m = _KEY.match(line.text)
            if not m:
                raise YamlError(f"line {line.no + 1}: expected 'key: value', got {line.text!r}")
            self.i += 1
            key = scalar(m.group("key"))
            out[key] = self.value_after(m.group("val"), line)
        return out

    def seq(self, indent: int) -> list:
        out: list = []
        while self.i < len(self.lines):
            line = self.lines[self.i]
            if line.indent != indent or not (line.text.startswith("- ") or line.text == "-"):
                break
            content = line.text[2:].strip() if line.text != "-" else ""
            self.i += 1
            if content == "":
                out.append(self.value_after(None, line))
                continue
            m = _KEY.match(content)
            if m and not content.startswith(("'", '"', "[", "{")) or (m and m.group("key")[0] in "'\"" and content.find(":") > 0):
                # "- key: value" starts a mapping whose keys sit at indent + 2
                item_indent = indent + 2
                item = {scalar(m.group("key")): self.value_after(m.group("val"), _Line(item_indent, content, line.raw, line.no))}
                if self.i < len(self.lines) and self.lines[self.i].indent == item_indent and not self.lines[self.i].text.startswith("- "):
                    item.update(self.mapping(item_indent))
                out.append(item)
            elif content[:1] in ("|", ">"):
                out.append(self.block_scalar(content, indent, line.no))
            else:
                out.append(scalar(content))
        return out


def parse(text: str) -> Any:
    return _Parser(text).parse()


# --------------------------------------------------------------------------- workflow model
@dataclass
class Step:
    data: dict

    @property
    def uses(self) -> str:
        return str(self.data.get("uses") or "")

    @property
    def run(self) -> str:
        return str(self.data.get("run") or "")

    @property
    def with_(self) -> dict:
        return self.data.get("with") or {}

    @property
    def name(self) -> str:
        return str(self.data.get("name") or self.uses or self.run.splitlines()[0] if self.run else "")


@dataclass
class Job:
    id: str
    data: dict
    steps: list[Step] = field(default_factory=list)

    @property
    def permissions(self) -> Any:
        return self.data.get("permissions")

    @property
    def condition(self) -> str:
        return str(self.data.get("if") or "")

    @property
    def needs(self) -> list[str]:
        n = self.data.get("needs") or []
        return [n] if isinstance(n, str) else list(n)

    @property
    def environment(self) -> Any:
        return self.data.get("environment")

    def runs(self) -> str:
        return "\n".join(s.run for s in self.steps)

    def uses_action(self, prefix: str) -> list[Step]:
        return [s for s in self.steps if s.uses.split("@")[0] == prefix]


@dataclass
class Workflow:
    path: str
    data: dict
    jobs: list[Job]

    @property
    def triggers(self) -> dict:
        on = self.data.get("on", self.data.get(True))
        if isinstance(on, str):
            return {on: None}
        if isinstance(on, list):
            return {t: None for t in on}
        return on or {}

    @property
    def permissions(self) -> Any:
        return self.data.get("permissions")

    def job(self, job_id: str) -> Job | None:
        return next((j for j in self.jobs if j.id == job_id), None)


def load(path: str, text: str) -> Workflow:
    data = parse(text)
    if not isinstance(data, dict):
        raise YamlError(f"{path}: a workflow must be a mapping")
    jobs = []
    for jid, jd in (data.get("jobs") or {}).items():
        jd = jd or {}
        jobs.append(Job(str(jid), jd, [Step(s) for s in jd.get("steps") or [] if isinstance(s, dict)]))
    return Workflow(path, data, jobs)
