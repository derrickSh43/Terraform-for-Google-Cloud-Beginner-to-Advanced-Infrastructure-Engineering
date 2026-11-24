"""Human-friendly terminal output."""

from __future__ import annotations

import os
import sys

from .runner import FAIL, PASS, SKIP, WARN, Report

_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
if os.name == "nt":
    os.system("")  # enables ANSI escape handling in Windows consoles

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except AttributeError:
    pass


def c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


ICON = {
    PASS: c("PASS", "32"),
    FAIL: c("FAIL", "31"),
    SKIP: c("SKIP", "90"),
    WARN: c("WARN", "33"),
}


def indent(text: str, n: int = 8) -> str:
    pad = " " * n
    return "\n".join(pad + line for line in text.splitlines())


def print_report(report: Report, verbose: bool = False) -> None:
    print()
    print(c(f"Lesson {report.lesson}  ({report.level})", "1"), c(str(report.target), "90"))
    print()
    print(c("Terraform checks", "1"))
    for st in report.stages:
        print(f"  {ICON[st.status]}  {st.name:<20} {st.summary}")
        if st.detail and (st.status == FAIL or verbose or st.status == WARN):
            print(indent(st.detail))
    if report.outcomes:
        print()
        print(c("Lab requirements", "1"))
        for o in report.outcomes:
            tag = c(" [challenge]", "35") if o.req.level == "challenge" else ""
            print(f"  {ICON[PASS] if o.passed else ICON[FAIL]}  {o.req.id:<7} {o.req.title}{tag}")
            if not o.passed:
                print(indent(c(o.message, "31")))
                if o.req.hint and not o.errored:
                    print(indent(c("hint: " + o.req.hint, "36")))
    elif any(s.status == FAIL for s in report.stages):
        print()
        print(c("  Requirement checks did not run - fix the failure above first.", "33"))

    print()
    total = len(report.outcomes)
    ok = sum(o.passed for o in report.outcomes)
    if report.passed:
        print(c(f"All checks passed ({ok}/{total} requirements).", "32;1"))
    else:
        print(c(f"Not passing yet: {ok}/{total} requirements met.", "31;1"))
    print()
