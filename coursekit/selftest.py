"""Course self-test: proves the validators themselves are correct.

For every lesson with status "ready":
  * starter          formats, inits and validates (and, for project lessons,
                     contains the previous lesson's solution unchanged)
  * solution         passes every lab requirement
  * solution-challenge passes every lab + challenge requirement
  * fixtures/*       each known-bad variant FAILS on the expected requirement
                     ids / stage (a validator that passes broken code is a bug)
  * broken/          the troubleshooting repo fails the way its ANSWER.md says
"""

from __future__ import annotations

import filecmp
import json
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from . import paths, runner
from .report import c


@dataclass
class Case:
    lesson: paths.Lesson
    name: str
    target: Path
    challenge: bool
    expect_pass: bool
    fail_ids: tuple[str, ...] = ()
    fail_stage: str | None = None
    tmp: Path | None = None
    starter: bool = False


@dataclass
class CaseResult:
    case: Case
    ok: bool
    message: str


def _overlay(base: Path, fixture: Path, delete: list[str]) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="course-fixture-"))
    shutil.copytree(base, tmp, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".terraform", "*.tfstate*"))
    for f in fixture.rglob("*"):
        if f.is_file() and f.name not in ("expect.json", "README.md"):
            dest = tmp / f.relative_to(fixture)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
    for d in delete:
        target = tmp / d
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink(missing_ok=True)
    return tmp


def _cases(lesson: paths.Lesson) -> tuple[list[Case], list[str]]:
    cases: list[Case] = []
    problems: list[str] = []

    if lesson.sub("starter").is_dir():
        cases.append(Case(lesson, "starter", lesson.sub("starter"), False, False, starter=True))
        prev = paths.previous_lesson(lesson)
        if lesson.project and prev and prev.status == "ready":
            for f in prev.sub("solution").rglob("*"):
                if f.is_file() and ".terraform" not in f.parts and f.name != ".terraform.lock.hcl":
                    twin = lesson.sub("starter") / lesson.starter_previous / f.relative_to(prev.sub("solution"))
                    if not twin.exists() or not filecmp.cmp(f, twin, shallow=False):
                        problems.append(f"starter/{f.relative_to(prev.sub('solution'))} differs from lesson {prev.id} solution")

    cases.append(Case(lesson, "solution", lesson.sub("solution"), False, True))
    if lesson.sub("solution-challenge").is_dir():
        cases.append(Case(lesson, "solution-challenge", lesson.sub("solution-challenge"), True, True))

    for exp in sorted(lesson.sub("fixtures").glob("*/expect.json")):
        spec = json.loads(exp.read_text(encoding="utf-8"))
        base = lesson.sub(spec.get("base", "solution"))
        tmp = _overlay(base, exp.parent, spec.get("delete", []))
        cases.append(
            Case(
                lesson,
                f"fixtures/{exp.parent.name}",
                tmp,
                spec.get("level", "lab") == "challenge",
                False,
                tuple(spec.get("fail_ids", [])),
                spec.get("fail_stage"),
                tmp=tmp,
            )
        )

    bexp = lesson.sub("broken") / "expect.json"
    if bexp.exists():
        spec = json.loads(bexp.read_text(encoding="utf-8"))
        tmp = _overlay(lesson.sub("broken"), Path(tempfile.mkdtemp()), [])
        cases.append(
            Case(lesson, "broken", tmp, False, False, tuple(spec.get("fail_ids", [])), spec.get("fail_stage"), tmp=tmp)
        )
    return cases, problems


def _state_is_fresh(lesson: paths.Lesson) -> list[str]:
    """A shipped state must match the previous lesson's solution exactly (plan = no changes)."""
    from . import terraform as tf

    prev = paths.previous_lesson(lesson)
    problems = []
    if not prev or not lesson.states:
        return problems
    for root_name, rel in lesson.states.items():
        if lesson.state_from == "starter":
            # the deployed environment includes things the starter adds (e.g. legacy resources to clean up)
            src, prev_root, who = lesson.sub("starter"), lesson.roots[root_name], "starter"
        else:
            # the state belongs to the same-named root of the previous lesson (or its only root)
            src, prev_root, who = prev.sub("solution"), prev.roots.get(root_name, prev.roots[prev.primary]), f"lesson {prev.id} solution"
        build = paths.BUILD / f"s{lesson.id}{root_name[:3]}"
        tf.sync_build_dir(src, build, roots=[prev_root], states={prev_root: lesson.path / rel})
        cwd = build / prev_root
        init = tf.run(["init", "-input=false", "-no-color", "-reconfigure"], cwd=cwd)
        res = tf.run(["plan", "-input=false", "-refresh=false", "-lock=false", "-no-color", "-detailed-exitcode", "-out=fresh.tfplan"], cwd=cwd)
        if init.ok and res.code == 2 and lesson.expected_drift:
            # a drift drill: only the declared addresses may differ, and only in place
            import json as _json
            show = _json.loads(tf.run(["show", "-json", "fresh.tfplan"], cwd=cwd).stdout)
            changed = {rc["address"]: rc["change"]["actions"] for rc in show.get("resource_changes", [])
                       if rc["change"]["actions"] != ["no-op"]}
            if changed and all(a in lesson.expected_drift and acts == ["update"] for a, acts in changed.items()):
                res.code = 0
        if not init.ok or res.code != 0:
            problems.append(f"{rel} is stale: {who} does not plan cleanly against it "
                            f"(regenerate with python -m coursekit.statefab)")
        starter_copy = lesson.sub("starter") / rel
        if starter_copy.exists() and not filecmp.cmp(starter_copy, lesson.path / rel, shallow=False):
            problems.append(f"starter/{rel} differs from {rel}")
    return problems


def _run(case: Case, idx: int) -> CaseResult:
    build = f"t{case.lesson.id}-{idx}"
    rep = runner.check(case.lesson, case.target, challenge=case.challenge, build_name=build, jobs=1)
    try:
        if case.starter:
            bad = {st for st in rep.failed_stages if st.split(" ")[0] in ("fmt", "init", "validate", "files")}
            return CaseResult(case, not bad, f"starter failed: {', '.join(sorted(bad))}" if bad else "")
        if case.expect_pass:
            if rep.passed:
                return CaseResult(case, True, "")
            why = sorted(rep.failed_stages) + sorted(rep.failed_ids)
            details = [o.message for o in rep.outcomes if not o.passed] + [s.detail for s in rep.stages if s.status == "fail"]
            return CaseResult(case, False, f"expected PASS, failed on {why}\n" + "\n".join(details)[:1500])
        if rep.passed:
            return CaseResult(case, False, "expected FAIL but every check passed (validator too lenient)")
        missing = [i for i in case.fail_ids if i not in rep.failed_ids]
        if missing:
            return CaseResult(case, False, f"expected {missing} to fail; failed: {sorted(rep.failed_ids) or sorted(rep.failed_stages)}")
        if case.fail_stage and not any(st.split(" ")[0] == case.fail_stage for st in rep.failed_stages):
            return CaseResult(case, False, f"expected stage '{case.fail_stage}' to fail; failed stages: {sorted(rep.failed_stages)}")
        return CaseResult(case, True, "")
    finally:
        if case.tmp:
            shutil.rmtree(case.tmp, ignore_errors=True)


def run(only: list[str] | None = None, workers: int = 4) -> bool:
    lessons = [l for l in paths.load_lessons() if l.status == "ready"]
    if only:
        keys = {k.lstrip("0") for k in only}
        lessons = [l for l in lessons if l.id.lstrip("0") in keys]

    all_cases: list[Case] = []
    problems: list[str] = []
    for lesson in lessons:
        cs, ps = _cases(lesson)
        ps += _state_is_fresh(lesson)
        all_cases += cs
        problems += [f"{lesson.dirname}: {p}" for p in ps]

    print(c(f"Self-testing {len(lessons)} lesson(s), {len(all_cases)} case(s)...", "1"))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(_run, all_cases, range(len(all_cases))))

    failures = 0
    current = None
    for r in results:
        if r.case.lesson.dirname != current:
            current = r.case.lesson.dirname
            print(c(f"\n{current}", "1"))
        mark = c("ok  ", "32") if r.ok else c("FAIL", "31")
        print(f"  {mark} {r.case.name}")
        if not r.ok:
            failures += 1
            print("       " + r.message.replace("\n", "\n       "))
    for p in problems:
        failures += 1
        print(c("  FAIL ", "31") + p)

    print()
    if failures:
        print(c(f"{failures} self-test failure(s).", "31;1"))
        return False
    print(c("All self-tests passed.", "32;1"))
    return True
