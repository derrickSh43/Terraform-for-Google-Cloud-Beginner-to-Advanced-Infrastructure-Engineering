"""Requirement-check framework used by every lesson's `checks.py`.

A lesson declares requirements like this:

    from coursekit.checks import requirement, require

    @requirement("R1.3", "Bucket uses uniform bucket-level access",
                 hint="Set uniform_bucket_level_access = true on the bucket.")
    def uniform_access(plan):
        bucket = one(plan, "google_storage_bucket")
        require(bucket.get("uniform_bucket_level_access") is True,
                "uniform_bucket_level_access is not enabled")

A check passes by returning normally and fails by calling `require(False, ...)`
(or raising CheckFailed). `level="challenge"` requirements only run with
`course check NN --challenge`. `test="name.tftest.hcl"` ties a requirement to a
lesson test: it only passes when that test passes too.
"""

from __future__ import annotations

import importlib.util
import sys
import threading
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .plan import Plan, Resource


class CheckFailed(Exception):
    pass


@dataclass
class Requirement:
    id: str
    title: str
    hint: str
    level: str
    func: Callable[[Plan], None]
    test: str = ""                  # a lesson test (*.tftest.hcl) that must also pass


@dataclass
class Outcome:
    req: Requirement
    passed: bool
    message: str = ""
    errored: bool = False


_REGISTRY: list[Requirement] = []
_LOAD_LOCK = threading.Lock()


def requirement(rid: str, title: str, *, hint: str = "", level: str = "lab", test: str = ""):
    if level not in ("lab", "challenge"):
        raise ValueError(f"level must be 'lab' or 'challenge', got {level!r}")

    def deco(func: Callable[[Plan], None]):
        _REGISTRY.append(Requirement(rid, title, hint, level, func, test))
        return func

    return deco


def require(condition: object, message: str) -> None:
    if not condition:
        raise CheckFailed(message)


def one(plan: Plan, rtype: str, what: str | None = None) -> Resource:
    """Return the single resource of a type, failing helpfully otherwise."""
    found = plan.resources(rtype)
    label = what or rtype
    require(found, f"No {label} found in the plan")
    require(len(found) == 1, f"Expected exactly one {label}, found {len(found)}: " + ", ".join(r.address for r in found))
    return found[0]


def at_least_one(plan: Plan, rtype: str, what: str | None = None) -> list[Resource]:
    found = plan.resources(rtype)
    require(found, f"No {what or rtype} found in the plan")
    return found


def load(checks_file: Path) -> list[Requirement]:
    """Import a lesson's checks.py and return its requirements in declared order."""
    with _LOAD_LOCK:
        return _load(checks_file)


def _load(checks_file: Path) -> list[Requirement]:
    _REGISTRY.clear()
    root = str(checks_file.resolve().parent.parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    name = f"lesson_checks_{abs(hash(str(checks_file)))}"
    spec = importlib.util.spec_from_file_location(name, checks_file)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    reqs = list(_REGISTRY)
    _REGISTRY.clear()
    ids = [r.id for r in reqs]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise RuntimeError(f"{checks_file}: duplicate requirement ids {sorted(dupes)}")
    return reqs


def run(reqs: list[Requirement], plan: Plan, challenge: bool) -> list[Outcome]:
    outcomes = []
    for req in reqs:
        if req.level == "challenge" and not challenge:
            continue
        try:
            req.func(plan)
            outcomes.append(Outcome(req, True))
        except CheckFailed as exc:
            outcomes.append(Outcome(req, False, str(exc)))
        except Exception:  # a validator bug or a very unexpected plan shape
            tb = traceback.format_exc(limit=3)
            outcomes.append(Outcome(req, False, "Validator error (report this to your instructor):\n" + tb, errored=True))
    return outcomes
