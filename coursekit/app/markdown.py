"""Small markdown -> HTML renderer for lesson pages (stdlib only).

Covers what the lessons use: headings, paragraphs, lists (nested by indent), blockquotes, fenced code
(mermaid kept as a diagram source block), pipe tables, inline code, bold/italic, links, horizontal rules.
"""

from __future__ import annotations

import html
import re

_FENCE = re.compile(r"^(\s*)(```+|~~~+)\s*([\w-]*)\s*$")


def inline(text: str) -> str:
    """Inline markdown on one line of text (escaped first)."""
    codes: list[str] = []

    def keep_code(m):
        codes.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", keep_code, text)
    text = html.escape(text, quote=False)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)",
                  lambda m: f'<a href="{html.escape(m.group(2))}" data-md-link>{m.group(1)}</a>', text)
    text = re.sub(r"(?<![\w&])<(https?://[^>\s]+)>", r'<a href="\1" target="_blank" rel="noopener">\1</a>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", text)
    text = re.sub(r"(?<![\w_])_([^_\n]+)_(?![\w_])", r"<em>\1</em>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)


def _table(rows: list[str]) -> str:
    def cells(line):
        line = line.strip().strip("|")
        return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line)]
    head = cells(rows[0])
    out = ["<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>"]
    for r in rows[2:]:
        out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cells(r)) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def _list(lines: list[str]) -> str:
    """Nested lists from indented '-', '*' or '1.' items (continuation lines join the item)."""
    items: list[list] = []                      # [indent, tag, text]
    for line in lines:
        m = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", line)
        if m:
            items.append([len(m.group(1)), "ol" if m.group(2)[0].isdigit() else "ul", m.group(3)])
        elif items:
            items[-1][2] += " " + line.strip()  # continuation line
    out: list[str] = []
    stack: list[tuple[int, str]] = []
    for ind, tag, text in items:
        if not stack or ind > stack[-1][0]:
            out.append(f"<{tag}>")              # new (possibly nested) list; parent <li> stays open
            stack.append((ind, tag))
        else:
            while len(stack) > 1 and ind < stack[-1][0]:
                out.append(f"</li></{stack.pop()[1]}>")
            out.append("</li>")
        out.append(f"<li>{inline(text)}")
    while stack:
        out.append(f"</li></{stack.pop()[1]}>")
    return "".join(out)


def render(md: str) -> str:
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    para: list[str] = []

    def flush():
        if para:
            out.append("<p>" + inline(" ".join(l.strip() for l in para)) + "</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        m = _FENCE.match(line)
        if m:
            flush()
            fence, lang, body = m.group(2), m.group(3).lower(), []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(fence[:3]):
                body.append(lines[i][len(m.group(1)):] if lines[i].startswith(m.group(1)) else lines[i])
                i += 1
            i += 1
            code = html.escape("\n".join(body))
            if lang == "mermaid":
                out.append(f'<pre class="mermaid-src" title="Diagram source (mermaid)"><code>{code}</code></pre>')
            else:
                out.append(f'<pre><code class="lang-{lang or "text"}">{code}</code></pre>')
            continue
        if not line.strip():
            flush()
            i += 1
            continue
        h = re.match(r"^(#{1,6})\s+(.*?)\s*#*$", line)
        if h:
            flush()
            n = len(h.group(1))
            out.append(f"<h{n}>{inline(h.group(2))}</h{n}>")
            i += 1
            continue
        if re.match(r"^\s*(-{3,}|\*{3,})\s*$", line):
            flush()
            out.append("<hr>")
            i += 1
            continue
        if line.lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{3,}", lines[i + 1]):
            flush()
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(lines[i])
                i += 1
            out.append(_table(rows))
            continue
        if line.startswith(">"):
            flush()
            quote = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(lines[i][1:].lstrip())
                i += 1
            out.append("<blockquote>" + render("\n".join(quote)) + "</blockquote>")
            continue
        if re.match(r"^\s*([-*+]|\d+[.)])\s+", line):
            flush()
            items = []
            while i < len(lines) and lines[i].strip() and not _FENCE.match(lines[i]):
                if not re.match(r"^\s*([-*+]|\d+[.)])\s+", lines[i]) and not lines[i].startswith((" ", "\t")):
                    break
                items.append(lines[i])
                i += 1
            # a fenced block indented under a list item belongs to it
            out.append(_list(items))
            continue
        para.append(line)
        i += 1
    flush()
    return "\n".join(out)
