"""Markdown reader for documentation requirements (lesson 24: ADRs, diagrams, failure analysis).

Stdlib only. It understands the subset students write: ATX headings (`## Title`), pipe tables,
fenced code blocks and `Key: value` lines. Checks use it to ask structural questions
("does every ADR have a Decision section with some substance?") and to read numbers out of
tables so they can be compared with what the plan says.

A rubric (`rubric.json` in a lesson folder) describes what a document must contain:

    {"adr": {"dir": "docs/adr", "name_pattern": "^[0-9]{4}-[a-z0-9-]+[.]md$", "min_records": 3,
             "status_values": ["Accepted", ...],
             "sections": [{"name": "Context", "aliases": [], "min_words": 40}, ...],
             "topics": [{"name": "disaster recovery", "any": ["rpo", "replica"]}, ...]},
     "criteria": [{"name": "Design", "covers": "..."}, ...]}
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```+|~~~+)\s*([\w-]*)")
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'/-]*")


def _lines_outside_fences(text: str) -> list[tuple[str, bool]]:
    """(line, inside_fence) pairs."""
    out, fence = [], None
    for line in text.splitlines():
        m = _FENCE.match(line)
        if m and (fence is None or m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence)):
            if fence is None:
                fence = m.group(1)
                out.append((line, True))
                continue
            fence = None
            out.append((line, True))
            continue
        out.append((line, fence is not None))
    return out


def headings(text: str) -> list[tuple[int, str]]:
    return [(len(m.group(1)), m.group(2).strip()) for line, fenced in _lines_outside_fences(text)
            if not fenced and (m := _HEADING.match(line))]


def title(text: str) -> str:
    h = [t for lvl, t in headings(text) if lvl == 1]
    return h[0] if h else ""


@dataclass
class Section:
    level: int
    title: str
    body: str

    @property
    def words(self) -> int:
        return words(self.body)


def sections(text: str) -> list[Section]:
    """Every heading with the text up to the next heading of the same or a higher level."""
    lines = _lines_outside_fences(text)
    marks = [(i, len(m.group(1)), m.group(2).strip()) for i, (line, fenced) in enumerate(lines)
             if not fenced and (m := _HEADING.match(line))]
    out = []
    for n, (i, lvl, ttl) in enumerate(marks):
        end = next((j for j, l2, _ in marks[n + 1:] if l2 <= lvl), len(lines))
        out.append(Section(lvl, ttl, "\n".join(l for l, _ in lines[i + 1:end])))
    return out


def find_section(text: str, *names: str) -> Section | None:
    """First section whose title starts with one of `names` (case-insensitive, ignoring numbering)."""
    wanted = [n.lower() for n in names]
    for s in sections(text):
        t = re.sub(r"^[0-9.\s]+", "", s.title).lower().strip()
        if any(t.startswith(w) for w in wanted):
            return s
    return None


def words(text: str) -> int:
    """Prose words: code blocks, table rules and markdown punctuation don't count."""
    prose = [l for l, fenced in _lines_outside_fences(text) if not fenced and not re.match(r"^\s*\|?\s*:?-{3,}", l)]
    return len(_WORD.findall("\n".join(prose)))


def fenced(text: str, lang: str | None = None) -> list[str]:
    """Contents of fenced code blocks (optionally only one language, e.g. 'mermaid')."""
    blocks, cur, cur_lang, fence = [], [], "", None
    for line in text.splitlines():
        m = _FENCE.match(line)
        if fence is None and m:
            fence, cur_lang, cur = m.group(1), m.group(2).lower(), []
            continue
        if fence is not None and m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not m.group(2):
            if lang is None or cur_lang == lang.lower():
                blocks.append("\n".join(cur))
            fence = None
            continue
        if fence is not None:
            cur.append(line)
    return blocks


def field(text: str, name: str) -> str | None:
    """Value of a `Name: value` line (also `**Name:** value` or `- Name: value`)."""
    pat = re.compile(rf"^\s*[-*]?\s*\**{re.escape(name)}\**\s*:\**\s*(.+?)\s*$", re.I | re.M)
    for line, fenced_ in _lines_outside_fences(text):
        if not fenced_ and (m := pat.match(line)):
            return m.group(1).strip("* ")
    return None


def clean_cell(cell: str) -> str:
    """Drop code ticks and surrounding bold/italic markers; keep underscores inside names."""
    c = cell.replace("`", "").strip()
    return re.sub(r"^[*_]+|[*_]+$", "", c).strip() if re.match(r"^[*_]", c) else c.strip("*").strip()


def tables(text: str) -> list[list[dict[str, str]]]:
    """Pipe tables as lists of rows; each row maps the (cleaned, lower-case) header to the cleaned cell."""
    out, rows = [], []
    lines = [l for l, fenced_ in _lines_outside_fences(text) if not fenced_] + [""]
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if line.startswith("|") and re.match(r"^\|?\s*:?-{3,}", nxt):
            header = [clean_cell(c).lower() for c in line.strip("|").split("|")]
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [clean_cell(c) for c in lines[i].strip().strip("|").split("|")]
                rows.append({h: (cells[k] if k < len(cells) else "") for k, h in enumerate(header)})
                i += 1
            out.append(rows)
            continue
        i += 1
    return out


def find_table(text: str, *column_patterns: str) -> tuple[list[dict[str, str]], list[str]] | None:
    """First table that has a column matching each regex; returns (rows, matched column names in order)."""
    for rows in tables(text):
        if not rows:
            continue
        cols = list(rows[0].keys())
        picked = []
        for pat in column_patterns:
            hit = next((c for c in cols if re.search(pat, c, re.I) and c not in picked), None)
            if hit is None:
                break
            picked.append(hit)
        else:
            return rows, picked
    return None


def number(cell: str) -> float | None:
    m = re.search(r"-?\d+(?:\.\d+)?", cell or "")
    return float(m.group(0)) if m else None


# ------------------------------------------------------------------ rubric
def load_rubric(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check_record(text: str, spec: dict) -> list[str]:
    """Problems with one decision record against the `adr` part of a rubric ([] = it passes)."""
    problems = []
    if not title(text):
        problems.append("no '# Title' heading")
    status = field(text, "Status")
    allowed = spec.get("status_values") or []
    if status is None:
        problems.append("no 'Status:' line")
    elif allowed and not any(status.lower().startswith(a.lower()) for a in allowed):
        problems.append(f"status {status!r} is not one of {allowed}")
    for sec in spec.get("sections", []):
        found = find_section(text, sec["name"], *sec.get("aliases", []))
        if found is None:
            problems.append(f"no '{sec['name']}' section")
        elif found.words < sec.get("min_words", 0):
            problems.append(f"'{found.title}' has {found.words} words - needs at least {sec['min_words']} to explain itself")
    return problems


def topics_covered(texts: list[str], topics: list[dict]) -> dict[str, bool]:
    lower = [t.lower() for t in texts]
    return {t["name"]: any(any(k.lower() in doc for k in t["any"]) for doc in lower) for t in topics}
