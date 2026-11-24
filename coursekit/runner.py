"""The `course check` pipeline: fmt -> init -> validate -> lint -> plan -> tests -> requirements."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
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


def check(lesson: paths.Lesson, target: Path, *, challenge: bool = False, build_name: str | None = None) -> Report:
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
    plans: dict[str, Plan] = {}
    for name, rdir in roots.items():
        suffix = f" ({name})" if multi else ""
        cwd = build / rdir

        # 2. init (uses the Terraform Registry through the shared plugin cache)
        init = tf.run(["init", "-input=false", "-no-color", "-reconfigure"], cwd=cwd)
        if not init.ok:
            report.stages.append(Stage("init" + suffix, FAIL, "terraform init failed", _with_hint(init.output, _init_hint(init.output))))
            return report
        report.stages.append(Stage("init" + suffix, PASS, "providers and modules installed" if multi else "providers installed"))

        # 3. validate
        val = tf.run(["validate", "-json", "-no-color"], cwd=cwd)
        if not val.ok:
            report.stages.append(Stage("validate" + suffix, FAIL, "configuration is invalid", _diagnostics(val.stdout) or val.output))
            return report
        report.stages.append(Stage("validate" + suffix, PASS, "configuration is valid"))

        # 4. tflint (optional)
        if shutil.which("tflint"):
            lint = subprocess.run(["tflint", "--no-color", f"--chdir={cwd}"], capture_output=True, text=True)
            status = PASS if lint.returncode == 0 else WARN
            report.stages.append(Stage("lint" + suffix, status, "tflint clean" if status == PASS else "tflint reported issues", lint.stdout.strip()))
        elif name == lesson.primary:
            report.stages.append(Stage("lint", SKIP, "tflint not installed (optional)"))

        # 4b. import blocks: the course plays the cloud's part (see coursekit.cloudsim)
        try:
            imported = cloudsim.apply(cwd, cloudsim.load_inventory(lesson.cloud_paths().get(rdir)))
        except cloudsim.ImportFailed as exc:
            report.stages.append(Stage("plan" + suffix, FAIL, "an import block can't be resolved", str(exc)))
            return report

        # 5. plan with a fake token -> plan JSON (against prepared state, if the lesson ships one)
        plan_res = tf.run(["plan", "-input=false", "-refresh=false", "-lock=false", "-no-color", "-out=course.tfplan"], cwd=cwd)
        if not plan_res.ok:
            report.stages.append(Stage("plan" + suffix, FAIL, "terraform plan failed", _with_hint(plan_res.output, _plan_hint(plan_res.output))))
            return report
        show = tf.run(["show", "-json", "course.tfplan"], cwd=cwd)
        plans[name] = Plan(json.loads(show.stdout), name=name, source=source, root=rdir)
        plans[name].imported = {i.address: i.id for i in imported}
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
        report.stages.append(Stage("plan" + suffix, PASS, summary, plan_res.stdout.strip()))  # full plan shown with -v
        (cwd / "plan.json").write_text(show.stdout, encoding="utf-8")

    plan = plans[lesson.primary]
    plan.others = {n: p for n, p in plans.items() if n != lesson.primary}

    # 6. terraform native tests (mock providers), if the lesson ships any
    if tests_dest.is_dir() and any(tests_dest.glob("*.tftest.hcl")):
        test = tf.run(["test", "-no-color"], cwd=build / primary_dir)
        summary = next((l for l in test.stdout.splitlines() if "passed" in l and "failed" in l), "")
        report.stages.append(Stage("tests", PASS if test.ok else FAIL, summary or ("tests passed" if test.ok else "tests failed"), "" if test.ok else test.output))

    # 6b. tests that students wrote for their own modules (modules/<name>/tests/*.tftest.hcl)
    for tdir in sorted(build.glob("modules/*/tests")):
        if not any(tdir.glob("*.tftest.hcl")):
            continue
        mdir = tdir.parent
        label = f"tests ({mdir.relative_to(build).as_posix()})"
        init = tf.run(["init", "-input=false", "-backend=false", "-no-color"], cwd=mdir)
        if not init.ok:
            report.stages.append(Stage(label, FAIL, "terraform init failed", init.output))
            continue
        test = tf.run(["test", "-no-color"], cwd=mdir)
        summary = next((l for l in test.stdout.splitlines() if "passed" in l and "failed" in l), "")
        report.stages.append(Stage(label, PASS if test.ok else FAIL, summary or ("tests passed" if test.ok else "tests failed"),
                                   "" if test.ok else test.output))

    # 7. requirement checks
    checks_file = lesson.sub("checks.py")
    if checks_file.exists():
        reqs = checks.load(checks_file)
        report.outcomes = checks.run(reqs, plan, challenge)
    return report
