"""Minimal, dependency-free reading of HCL source for facts the plan JSON omits.

Plan JSON leaves out backend blocks, `lifecycle` meta-arguments and per-module
`terraform` blocks. Checks needing them use this module. It understands block
nesting, strings and comments well enough for well-formed (`terraform fmt`ed)
code, but it doesn't evaluate expressions. Prefer plan-based checks whenever
the plan can answer the question.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Block:
    type: str
    labels: list[str]
    body: str
    file: str
    children: list["Block"] = field(default_factory=list)

    def attr(self, name: str) -> str | None:
        """Raw expression of a top-level attribute in this block (quotes stripped for plain strings)."""
        depth = 0
        for line in self.body.splitlines():
            stripped = line.strip()
            if depth == 0:
                m = re.match(rf"^{re.escape(name)}\s*=\s*(.+?)\s*$", stripped)
                if m:
                    val = m.group(1)
                    if len(val) >= 2 and val[0] == '"' and val[-1] == '"' and '"' not in val[1:-1]:
                        return val[1:-1]
                    return val
            depth += _brace_delta(stripped)
        return None

    def blocks(self, btype: str, *labels: str) -> list["Block"]:
        return [b for b in self.children if b.type == btype and list(b.labels[: len(labels)]) == list(labels)]

    def block(self, btype: str, *labels: str) -> "Block | None":
        found = self.blocks(btype, *labels)
        return found[0] if found else None


def _strip_comments(text: str) -> str:
    out, i, n = [], 0, len(text)
    in_str = False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
        elif ch == "#" or (ch == "/" and i + 1 < n and text[i + 1] == "/"):
            while i < n and text[i] != "\n":
                i += 1
        elif ch == "/" and i + 1 < n and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _brace_delta(line: str) -> int:
    line = re.sub(r'"(?:[^"\\]|\\.)*"', '""', line)
    return line.count("{") - line.count("}")


_HEADER = re.compile(r'^\s*([A-Za-z_][\w-]*)((?:\s+"[^"]*"|\s+[A-Za-z_][\w-]*)*)\s*\{\s*$')
_ONE_LINE = re.compile(r'^\s*([A-Za-z_][\w-]*)((?:\s+"[^"]*"|\s+[A-Za-z_][\w-]*)*)\s*\{(.*)\}\s*$')


def parse(text: str, file: str = "") -> list[Block]:
    """Parse blocks (recursively). Attributes stay as raw text in Block.body."""
    lines = _strip_comments(text).splitlines()
    return _parse_lines(lines, 0, len(lines), file)


def _parse_lines(lines: list[str], start: int, end: int, file: str) -> list[Block]:
    blocks: list[Block] = []
    i = start
    while i < end:
        one = _ONE_LINE.match(lines[i])
        if one and _brace_delta(lines[i]) == 0:
            labels = [l.strip().strip('"') for l in re.findall(r'"[^"]*"|[A-Za-z_][\w-]*', one.group(2) or "")]
            blocks.append(Block(one.group(1), labels, one.group(3).strip(), file, []))
            i += 1
            continue
        m = _HEADER.match(lines[i])
        if not m:
            i += 1
            continue
        btype = m.group(1)
        labels = [l.strip().strip('"') for l in re.findall(r'"[^"]*"|[A-Za-z_][\w-]*', m.group(2) or "")]
        depth = 1
        j = i + 1
        while j < end and depth > 0:
            depth += _brace_delta(lines[j])
            j += 1
        body_lines = lines[i + 1 : j - 1]
        blocks.append(Block(btype, labels, "\n".join(body_lines), file, _parse_lines(body_lines, 0, len(body_lines), file)))
        i = j
    return blocks


class Source:
    """All .tf files of a student's tree, keyed by path relative to the tree root."""

    def __init__(self, files: dict[str, str], docs: dict[str, str] | None = None, paths: set[str] | None = None):
        self.files = files
        self.docs = docs or {}            # markdown: docs/**/*.md and top-level *.md (lesson 24)
        self.paths = paths or set(files)  # every file in the tree (relative, posix)
        self._parsed = {name: parse(text, name) for name, text in files.items()
                        if name.endswith((".tf", ".tfvars", ".tftest.hcl"))}

    @classmethod
    def from_dir(cls, root: Path) -> "Source":
        files = {}
        found = list(root.rglob("*.tf")) + list(root.rglob("*.tfvars")) + list(root.rglob("*.tftest.hcl"))
        wf_dir = root / ".github" / "workflows"
        if wf_dir.is_dir():
            found += list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml"))
        for p in sorted(found):
            if ".terraform" in p.parts or p.name.startswith("zz_course_"):
                continue
            files[p.relative_to(root).as_posix()] = p.read_text(encoding="utf-8", errors="replace")
        docs = {}
        md = list(root.glob("*.md")) + (list((root / "docs").rglob("*.md")) if (root / "docs").is_dir() else [])
        for p in sorted(md):
            docs[p.relative_to(root).as_posix()] = p.read_text(encoding="utf-8", errors="replace")
        every = {p.relative_to(root).as_posix() for p in root.rglob("*")
                 if p.is_file() and ".terraform" not in p.parts and not p.name.startswith("zz_course_")}
        return cls(files, docs, every)

    def blocks(self, btype: str, *labels: str, under: str = "", recursive: bool = True) -> list[Block]:
        """Top-level blocks of a type in files under directory `under` ('' = everywhere)."""
        out = []
        prefix = under.rstrip("/") + "/" if under else ""
        for name, blocks in self._parsed.items():
            if prefix and not name.startswith(prefix):
                continue
            if not recursive and "/" in name[len(prefix):]:
                continue
            out += [b for b in blocks if b.type == btype and list(b.labels[: len(labels)]) == list(labels)]
        return out

    def backend(self, root: str) -> Block | None:
        for tf_block in self.blocks("terraform", under=root, recursive=False):
            for b in tf_block.children:
                if b.type == "backend":
                    return b
        return None

    def workflows(self) -> list:
        """GitHub Actions workflows in .github/workflows (parse errors raise coursekit.workflow.YamlError)."""
        from . import workflow
        return [workflow.load(n, t) for n, t in sorted(self.files.items())
                if n.startswith(".github/workflows/") and n.endswith((".yml", ".yaml"))]

    def test_files(self, under: str = "") -> dict[str, list[Block]]:
        """Parsed .tftest.hcl files under a directory: path -> top-level blocks."""
        prefix = under.rstrip("/") + "/" if under else ""
        return {n: b for n, b in self._parsed.items() if n.endswith(".tftest.hcl") and n.startswith(prefix)}

    def tfvars(self, under: str = "") -> dict[str, str]:
        """tfvars files (path -> text) under a directory."""
        prefix = under.rstrip("/") + "/" if under else ""
        return {n: t for n, t in self.files.items() if n.endswith(".tfvars") and n.startswith(prefix)}

    def dirs(self, under: str) -> list[str]:
        prefix = under.rstrip("/") + "/"
        return sorted({name[len(prefix):].split("/")[0] for name in self.files if name.startswith(prefix) and "/" in name[len(prefix):]})
