"""Re-run requirements from earlier lessons against today's plans (lesson 24 baselines).

A capstone requirement can say "these lesson 10 and lesson 19 requirements must still hold":

    from coursekit import baseline

    @requirement("R24.2", "Phase 2 baselines still hold")
    def phase2(plan):
        baseline.require_all(plan, ["R6.1", "R10.1", "R10.2"])

Requirement IDs map to lessons by their number (R10.2 -> lesson 10). Only pick requirements that
are about the *platform* (security, structure, behaviour), not one-off migrations
("deployed dev changes safely" against that lesson's prepared state, move/import exercises).
"""

from __future__ import annotations

import re
import threading

from . import checks, paths
from .checks import require

_CACHE: dict[str, dict[str, checks.Requirement]] = {}
_LOCK = threading.Lock()


def _lesson_reqs(lesson_id: str) -> dict[str, checks.Requirement]:
    with _LOCK:
        if lesson_id not in _CACHE:
            lesson = next((l for l in paths.load_lessons() if l.id == lesson_id), None)
            if lesson is None or not lesson.sub("checks.py").exists():
                raise KeyError(f"no checks for lesson {lesson_id}")
            _CACHE[lesson_id] = {r.id: r for r in checks.load(lesson.sub("checks.py"))}
        return _CACHE[lesson_id]


def requirement_for(rid: str) -> checks.Requirement:
    m = re.match(r"^[RC](\d+)\.\d+$", rid)
    if not m:
        raise KeyError(f"not a requirement id: {rid}")
    reqs = _lesson_reqs(f"{int(m.group(1)):02d}")
    if rid not in reqs:
        raise KeyError(f"lesson {m.group(1)} has no requirement {rid}")
    return reqs[rid]


def run(plan, ids: list[str]) -> list[checks.Outcome]:
    return checks.run([requirement_for(i) for i in ids], plan, challenge=True)


def require_all(plan, ids: list[str]) -> None:
    """Fail with every broken baseline (id, title, first lines of its message)."""
    failed = [o for o in run(plan, ids) if not o.passed]
    lines = []
    for o in failed:
        msg = "\n      ".join(o.message.strip().splitlines()[:4])
        lines.append(f"{o.req.id} {o.req.title}\n      {msg}")
    require(not failed, f"{len(failed)} of {len(ids)} baseline requirement(s) no longer hold:\n  " + "\n  ".join(lines))
