"""The `course check` pipeline: fmt -> init -> validate -> lint -> plan -> tests -> requirements."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from . import checks, cloudsim, paths
from . import terraform as tf
from .hcl import Source
from .plan import Plan

PASS, FAIL, SKIP, WARN = "pass", "fail", "skip", "warn"


@dataclass
class Stage:
    name: str
    status: str
    summary: str = ""
    detail: str = ""


@dataclass
class Report:
    lesson: str
    target: Path
    level: str
    stages: list[Stage] = field(default_factory=list)
    outcomes: list[checks.Outcome] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(s.status in (PASS, SKIP, WARN) for s in self.stages) and all(o.passed for o in self.outcomes)

    @property
    def failed_ids(self) -> set[str]:
        return {o.req.id for o in self.outcomes if not o.passed}

    @property
    def failed_stages(self) -> set[str]:
        return {s.name for s in self.stages if s.status == FAIL}

    def to_json(self) -> dict:
        return {
            "lesson": self.lesson,
            "target": str(self.target),
            "level": self.level,
            "passed": self.passed,
            "stages": [s.__dict__ for s in self.stages],
            "requirements": [
                {"id": o.req.id, "title": o.req.title, "level": o.req.level, "passed": o.passed, "message": o.message, "hint": o.req.hint}
                for o in self.outcomes
            ],
        }


def _diagnostics(validate_json: str) -> str:
    try:
        data = json.loads(validate_json)
    except json.JSONDecodeError:
        return validate_json
    lines = []
    for d in data.get("diagnostics", []):
        rng = d.get("range") or {}
        where = f"{rng.get('filename', '?')}:{rng.get('start', {}).get('line', '?')}" if rng else ""
        lines.append(f"[{d.get('severity', 'error')}] {where} {d.get('summary', '')}".strip())
        if d.get("detail"):
            lines.append("    " + d["detail"].replace("\n", "\n    "))
    return "\n".join(lines)


def _with_hint(output: str, hint: str) -> str:
    """Hint first: Terraform's own output (e.g. a whole plan) can be long."""
    if not hint:
        return output.strip()
    return f"{hint}\n\n--- terraform output ---\n{output.strip()}"


def _plan_hint(output: str) -> str:
    if re.search(r"401|invalid authentication|Invalid Credentials", output, re.I):
        ds = re.search(r"with (data\.[\w-]+\.[\w-]+)", output)
        loc = re.search(r"on (\S+) line (\d+)", output)
        what = f"`{ds.group(1)}`" if ds else "A data source"
        where = f" ({loc.group(1)} line {loc.group(2)})" if loc else ""
        return (
            f"{what}{where} tries to read live Google Cloud data during plan, which can't work offline.\n"
            "Data sources call the GCP API at plan time; resources don't until apply. Remove the data\n"
            "source and use a variable instead (set its value in terraform.tfvars) - the lesson says which.\n"
            "Only data sources that resolve locally (e.g. google_client_config) work in course labs."
        )
    if "No value for required variable" in output:
        return "Give the variable a value in terraform.tfvars (or a default) - checks run with -input=false."
    return ""


def _init_hint(output: str) -> str:
    flat = " ".join(output.split())         # Terraform wraps long lines
    m = re.search(r"does not have a provider named (?:registry\.terraform\.io/)?([\w.-]+)/([\w.-]+)", flat)
    if m:
        ns, name = m.groups()
        fix = f'"hashicorp/{name}"' if ns != "hashicorp" else "the provider's exact name from registry.terraform.io"
        return (
            f'There is no provider called "{ns}/{name}" in the Terraform Registry - check the spelling of `source`\n'
            f"in required_providers (usually versions.tf). Did you mean {fix}?"
        )
    if re.search(r"registry\.terraform\.io|could not connect|Failed to query available provider", output, re.I):
        return (
            "Terraform could not reach the Terraform Registry. Check your internet connection, or run\n"
            "`python course.py setup` while online so providers are cached for offline use."
        )
    if "locked provider" in output or "dependency lock file" in output:
        return "Your .terraform.lock.hcl disagrees with required_providers. Delete it and re-run the check."
    return ""


def _test_hint(output: str, dirs: list[Path] | tuple[Path, ...] = ()) -> str:
    """Explain a failing lesson test. `dirs` hold the configuration the tests run against."""
    flat = " ".join(output.split())         # Terraform wraps long lines
    m = re.search(r'managed resource "([\w-]+)" "([\w-]+)" has not been declared', flat)
    if m:
        rtype, name = m.groups()
        code = "\n".join(f.read_text(encoding="utf-8", errors="replace") for d in dirs for f in sorted(d.glob("*.tf")))
        mine = sorted(set(re.findall(rf'(?m)^resource\s+"{re.escape(rtype)}"\s+"([\w-]+)"', code)))
        yours = " Yours: " + ", ".join(f'"{n}"' for n in mine) + "." if mine else ""
        return (
            f"The test looks for a resource named `{rtype}.{name}`, and your code doesn't have one.{yours}\n"
            f'Declare it as `resource "{rtype}" "{name}"`, and update everything that refers to the old name.'
        )
    extra = set(re.findall(r'does not declare a variable named "([\w-]+)"', flat))      # the test sets these
    m = re.search(r'has a required variable "([\w-]+)" with no set value', flat)
    if m:
        hint = (f'The test doesn\'t set "{m.group(1)}", and it has no default. Give the variable a default,\n'
                "so callers that don't care about it can leave it out.")
        if extra:
            hint += "\nOr is it named differently? The test sets " + ", ".join(f'"{n}"' for n in sorted(extra)) + ", which your code doesn't declare."
        return hint
    m = re.search(r"Missing expected failure.*?checkable object, var[.]([\w-]+),", flat)
    if m and m.group(1) in extra:
        return f'The test sets a variable named "{m.group(1)}", and your code doesn\'t declare it.'
    if m:
        return f"The test passes a bad value to var.{m.group(1)} and your code accepted it. Check the condition in its validation block."
    return ""


def _test_results(output: str) -> dict[str, bool]:
    """{"name.tftest.hcl": passed} from `terraform test` output."""
    found = re.findall(r"(?m)^(\S+[.]tftest[.]hcl)[.]{3} (pass|fail|skip|error)\s*$", output)
    return {re.split(r"[\\/]", path)[-1].removeprefix("lesson_"): result == "pass" for path, result in found}


def _apply_tests(outcomes: list[checks.Outcome], results: dict[str, bool]) -> None:
    """A requirement proven by a lesson test only passes when that test does."""
    for o in outcomes:
        if o.req.test and o.passed and not results.get(o.req.test, False):
            o.passed = False
            o.message = (f"The lesson test {o.req.test} fails: see the failed tests stage" if o.req.test in results
                         else f"The lesson test {o.req.test} did not run: see the failed stages, or check the module's folder name")


def check(lesson: paths.Lesson, target: Path, *, challenge: bool = False, build_name: str | None = None, jobs: int = 3) -> Report:
    level = "challenge" if challenge else "lab"
    report = Report(lesson.dirname, target, level)
    if not target.is_dir():
        report.stages.append(Stage("files", FAIL, f"{target} does not exist", "Run `python course.py start {}` first.".format(lesson.id)))
        return report
    if not tf.tf_files(target):
        report.stages.append(Stage("files", FAIL, "no .tf files found", str(target)))
        return report

    # 1. formatting (non-blocking, but must pass for the lab to pass)
    fmt = tf.run(["fmt", "-check", "-recursive", "-list=true", "-no-color", str(target)], cwd=target)
    if fmt.ok:
        report.stages.append(Stage("fmt", PASS, "all files are canonically formatted"))
    else:
        files = [l for l in fmt.stdout.splitlines() if l.strip()]
        report.stages.append(
            Stage("fmt", FAIL, f"{len(files)} file(s) need formatting", "\n".join(files) + "\nFix with: terraform fmt -recursive")
        )

    build = paths.BUILD / (build_name or f"{lesson.id}{level[0]}")  # short: Windows MAX_PATH
    roots = lesson.roots                       # {"dev": "envs/dev", ...} or {"main": ""}
    multi = len(roots) > 1 or next(iter(roots.values())) != ""
    primary_dir = roots[lesson.primary]
    tests_dir = lesson.sub("tests") / level
    tf.sync_build_dir(
        target,
        build,
        extra=tests_dir if tests_dir.is_dir() else None,
        roots=list(roots.values()),
        states=lesson.state_paths(),
    )
    tests_dest = build / primary_dir / "tests"
    if challenge and (lesson.sub("tests") / "lab").is_dir():
        for f in (lesson.sub("tests") / "lab").glob("*.tftest.hcl"):
            tests_dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, tests_dest / f.name)

    # Lesson tests for a specific module (tests/<level>/modules/<name>/*.tftest.hcl) run inside
    # that module's folder - needed e.g. for modules with configuration_aliases.
    for lvl in (["lab", "challenge"] if challenge else ["lab"]):
        for mtests in sorted((lesson.sub("tests") / lvl / "modules").glob("*")):
            dest = build / "modules" / mtests.name / "tests"
            if mtests.is_dir() and (build / "modules" / mtests.name).is_dir():
                dest.mkdir(parents=True, exist_ok=True)
                for f in mtests.glob("*.tftest.hcl"):
                    shutil.copy2(f, dest / f"lesson_{f.name}")

    missing = [d for d in roots.values() if not (target / d).is_dir() or not list((target / d).glob("*.tf"))]
    if missing:
        report.stages.append(Stage("files", FAIL, "missing root module folder(s): " + ", ".join(missing),
                                   "Each of these folders needs .tf files: " + ", ".join(roots.values())))
        return report

    source = Source.from_dir(target)

    def one_root(name: str, rdir: str) -> tuple[list[Stage], Plan | None]:
        suffix = f" ({name})" if multi else ""
        cwd = build / rdir
        stages: list[Stage] = []

        # 2. init (uses the Terraform Registry through the shared plugin cache)
        init = tf.run(["init", "-input=false", "-no-color", "-reconfigure"], cwd=cwd)
        if not init.ok:
            return [Stage("init" + suffix, FAIL, "terraform init failed", _with_hint(init.output, _init_hint(init.output)))], None
        stages.append(Stage("init" + suffix, PASS, "providers and modules installed" if multi else "providers installed"))

        # 3. validate. `plan` validates too, so this only runs when there's something to explain
        # (the plan failed), or when cloudsim is about to read import blocks.
        def validate() -> bool:
            val = tf.run(["validate", "-json", "-no-color"], cwd=cwd)
            stages.append(Stage("validate" + suffix, PASS, "configuration is valid") if val.ok else
                          Stage("validate" + suffix, FAIL, "configuration is invalid", _diagnostics(val.stdout) or val.output))
            return val.ok

        has_imports = any(re.search(r"(?m)^\s*import\s*\{", f.read_text(encoding="utf-8", errors="replace")) for f in cwd.glob("*.tf"))
        if has_imports and not validate():
            return stages, None

        # 4. import blocks: the course plays the cloud's part (see coursekit.cloudsim)
        try:
            imported = cloudsim.apply(cwd, cloudsim.load_inventory(lesson.cloud_paths().get(rdir)))
        except cloudsim.ImportFailed as exc:
            stages.append(Stage("plan" + suffix, FAIL, "an import block can't be resolved", str(exc)))
            return stages, None

        # 5. plan with a fake token -> plan JSON (against prepared state, if the lesson ships one)
        plan_res = tf.run(["plan", "-input=false", "-refresh=false", "-lock=false", "-no-color", "-out=course.tfplan"], cwd=cwd)
        if not plan_res.ok:
            if has_imports or validate():
                stages.append(Stage("plan" + suffix, FAIL, "terraform plan failed", _with_hint(plan_res.output, _plan_hint(plan_res.output))))
            return stages, None
        if not has_imports:
            stages.append(Stage("validate" + suffix, PASS, "configuration is valid"))

        # 5b. tflint (optional)
        if shutil.which("tflint"):
            lint = subprocess.run(["tflint", "--no-color", f"--chdir={cwd}"], capture_output=True, text=True)
            status = PASS if lint.returncode == 0 else WARN
            stages.append(Stage("lint" + suffix, status, "tflint clean" if status == PASS else "tflint reported issues", lint.stdout.strip()))
        elif name == lesson.primary:
            stages.append(Stage("lint", SKIP, "tflint not installed (optional)"))

        show = tf.run(["show", "-json", "course.tfplan"], cwd=cwd)
        if not show.ok:
            stages.append(Stage("plan" + suffix, FAIL, "terraform could not read the plan", show.output))
            return stages, None
        plan = Plan(json.loads(show.stdout), name=name, source=source, root=rdir)
        plan.imported = {i.address: i.id for i in imported}
        counts = re.search(r"Plan: (\d+) to add, (\d+) to change, (\d+) to destroy", plan_res.stdout)
        if counts:
            summary = counts.group(0)
        elif "No changes" in plan_res.stdout:
            summary = "No changes. Infrastructure matches the configuration."
        else:
            summary = "plan succeeded"
        if rdir in lesson.state_paths():
            summary += "  [against deployed state]"
        if imported:
            summary += f"  [{len(imported)} imported (simulated)]"
        stages.append(Stage("plan" + suffix, PASS, summary, plan_res.stdout.strip()))  # full plan shown with -v
        (cwd / "plan.json").write_text(show.stdout, encoding="utf-8")
        return stages, plan

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        results = list(pool.map(lambda r: one_root(*r), roots.items()))
    plans: dict[str, Plan] = {}
    for name, (stages, plan) in zip(roots, results):
        report.stages += stages
        if plan is None:
            return report                   # explain one broken root at a time
        plans[name] = plan

    plan = plans[lesson.primary]
    plan.others = {n: p for n, p in plans.items() if n != lesson.primary}

    test_results: dict[str, bool] = {}

    def run_tests(label: str, cwd: Path, dirs: list[Path]) -> Stage:
        test = tf.run(["test", "-no-color"], cwd=cwd)
        test_results.update(_test_results(test.output))
        summary = next((l for l in test.stdout.splitlines() if "passed" in l and "failed" in l), "")
        return Stage(label, PASS if test.ok else FAIL, summary or ("tests passed" if test.ok else "tests failed"),
                     "" if test.ok else _with_hint(test.output, _test_hint(test.output, dirs)))

    def primary_tests() -> Stage:
        modules = {m for f in tests_dest.glob("*.tftest.hcl") for m in re.findall(r"modules/([\w-]+)", f.read_text(encoding="utf-8"))}
        return run_tests("tests", build / primary_dir, [build / primary_dir, *(build / "modules" / m for m in sorted(modules))])

    def module_tests(mdir: Path) -> Stage:
        label = f"tests ({mdir.relative_to(build).as_posix()})"
        lock = mdir / ".terraform.lock.hcl"
        if not (target / mdir.relative_to(build) / lock.name).exists() and paths.SHARED_LOCK.exists():
            shutil.copy2(paths.SHARED_LOCK, lock)      # same provider as the roots, from the cache
        init = tf.run(["init", "-input=false", "-backend=false", "-no-color"], cwd=mdir)
        return run_tests(label, mdir, [mdir]) if init.ok else Stage(label, FAIL, "terraform init failed", init.output)

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        # 6. terraform native tests (mock providers), if the lesson ships any
        pending = [pool.submit(primary_tests)] if tests_dest.is_dir() and any(tests_dest.glob("*.tftest.hcl")) else []
        # 6b. tests inside modules (modules/<name>/tests/*.tftest.hcl): written by the student, or by the lesson
        pending += [pool.submit(module_tests, d.parent) for d in sorted(build.glob("modules/*/tests")) if any(d.glob("*.tftest.hcl"))]
        report.stages += [f.result() for f in pending]

    # 7. requirement checks
    checks_file = lesson.sub("checks.py")
    if checks_file.exists():
        reqs = checks.load(checks_file)
        report.outcomes = checks.run(reqs, plan, challenge)
        _apply_tests(report.outcomes, test_results)
    return report
