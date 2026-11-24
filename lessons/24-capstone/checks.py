"""Lesson 24 - Advanced System Design: Capstone.

`plan` is dev against the deployed lesson 23 environment (it must not change); `plan.others` holds
prod, hub, platform and bootstrap. Three kinds of checks:

* baselines - selected lab requirements of lessons 01-23, re-run against today's plans (coursekit.baseline);
* automation and tests - the workflow (coursekit.workflow) and module tests (run by the test stage);
* documentation - markdown read with coursekit.docs, measured against rubric.json, and compared with
  what the plans say (the failure analysis must match coursekit.failure's numbers).
"""

import re
from pathlib import Path

from coursekit import baseline, docs, failure
from coursekit.checks import require, requirement
from coursekit.plan import strip_index
from coursekit.workflow import YamlError

RUBRIC = docs.load_rubric(Path(__file__).with_name("rubric.json"))
ENV_ROOTS = ["dev", "prod", "hub", "platform"]
ALL_ROOTS = ["envs/dev", "envs/prod", "envs/hub", "envs/platform", "bootstrap"]
AUTH = "google-github-actions/auth"
PLATFORM_MODULES = ("landing-zone", "project-factory", "central-logging")
OBJECTIVE_STORES = {
    "database": lambda s: s.kind == "sql",
    "backups": lambda s: s.address == "module.foundation.google_storage_bucket.backups",
    "images": lambda s: s.kind == "registry",
}


def _ids(spec):
    """'R12.1-6 R13.1' -> ['R12.1', ..., 'R12.6', 'R13.1']"""
    out = []
    for tok in spec.split():
        m = re.match(r"^(R\d+)\.(\d+)-(\d+)$", tok)
        out += [f"{m.group(1)}.{i}" for i in range(int(m.group(2)), int(m.group(3)) + 1)] if m else [tok]
    return out


# Platform properties only: one-off migrations and "deployed dev changes safely against lesson N's
# state" are left out, and so are lesson 16's single-pipeline shape checks (R16.6/R16.7),
# which R24.5 replaces for five roots.
PHASE1 = _ids("R1.1-3 R2.1 R2.2 R2.4 R2.6 R5.4 R5.5")
PHASE2 = _ids("R6.1-5 R6.7 R7.2 R8.1-3 R8.9 R9.1 R9.6 R9.10 R10.1-3 R10.5-7 R10.10 R11.7")
PHASE3 = _ids("R12.1-6 R13.1 R13.8 R14.1-5 R14.7 R14.10 R15.1-8 R15.10 R16.1-5 R16.8 R16.9 R17.1-9")
PHASE4 = _ids("R18.1-9 R19.1-8 R19.10 R20.1 R20.4 R20.8 R20.9 R21.1-7 R21.10 R22.1-8 R22.10 R23.1-9")


# ------------------------------------------------------------------ helpers: workflow
def _wf(plan):
    try:
        wfs = [w for w in plan.source.workflows() if w.jobs]
    except YamlError as exc:
        require(False, f"Workflow file can't be parsed: {exc}")
    require(wfs, "No GitHub Actions workflow with jobs in .github/workflows/")
    require(len(wfs) == 1, f"Keep one Terraform workflow (found {[w.path for w in wfs]}) - lesson 16's checks read it")
    return wfs[0]


def _tf_lines(job, verb):
    return [l for l in job.runs().splitlines() if re.search(rf"terraform\b.*\b{verb}\b", l)]


def _matrix(job):
    return ((job.data.get("strategy") or {}).get("matrix") or {})


def _roots(job, verb):
    """Root dirs the job runs `terraform <verb>` in (literal paths or envs/${{ matrix.x }})."""
    found = set()
    for line in _tf_lines(job, verb):
        found |= {f"envs/{r}" for r in re.findall(r"envs/([a-z0-9_-]+)", line)}
        for key in re.findall(r"envs/\$\{\{\s*matrix\.([\w-]+)\s*\}\}", line):
            found |= {f"envs/{v}" for v in _matrix(job).get(key) or []}
        if re.search(r"envs/\*", line):
            found |= {f"envs/{r}" for r in ENV_ROOTS}
        if "bootstrap" in line:
            found.add("bootstrap")
    if verb == "validate" and re.search(r"for\s+\w+\s+in\s+([^;\n]+)", job.runs()):
        loop = re.search(r"for\s+\w+\s+in\s+([^;\n]+)", job.runs()).group(1)
        found |= {t.rstrip("/") for t in loop.split() if t.rstrip("/") in ALL_ROOTS}
        if "envs/*" in loop:
            found |= {f"envs/{r}" for r in ENV_ROOTS}
    return found


def _environment(job, root):
    env = job.environment
    if isinstance(env, dict):
        env = env.get("name")
    env = str(env or "")
    m = re.search(r"\$\{\{\s*matrix\.([\w-]+)\s*\}\}", env)
    if m:
        vals = [str(v) for v in _matrix(job).get(m.group(1)) or []]
        env = env.replace(m.group(0), root.split("/")[-1] if root.split("/")[-1] in vals else "?")
    return env


def _needs_all(wf, job, seen=None):
    seen = set() if seen is None else seen
    for n in job.needs:
        if n not in seen:
            seen.add(n)
            j = wf.job(n)
            if j is not None:
                _needs_all(wf, j, seen)
    return seen


def _sa(job):
    a = job.uses_action(AUTH)
    return str(a[0].with_.get("service_account")) if a else ""


def _apply_jobs(wf, root):
    return [j for j in wf.jobs if root in _roots(j, "apply")]


def _pr_plan_jobs(wf):
    return [j for j in wf.jobs if _tf_lines(j, "plan") and "pull_request" in j.condition]


# ------------------------------------------------------------------ helpers: docs
def _doc(plan, path, what):
    text = plan.source.docs.get(path)
    require(text is not None, f"{path} not found - {what}")
    return text


def _cell_matches(cell, address):
    c = cell.strip()
    return c == address or c == strip_index(address)


def _match_workload(cell, workloads):
    exact = [w for w in workloads if _cell_matches(cell, w.address)]
    if exact:
        return exact
    c = cell.strip()
    return [w for w in workloads if c and c in w.address] if c.startswith("module.") or "google_" in c else []


# ------------------------------------------------------------------ lab
@requirement("R24.1", "Phase 1 baselines still hold (lessons 01-05: providers, APIs, basic IAM, firewalls)",
             hint="Run `python course.py check NN` on an earlier lesson for the full explanation of a failing requirement")
def phase1(plan):
    baseline.require_all(plan, PHASE1)


@requirement("R24.2", "Phase 2 baselines still hold (lessons 06-11: state, modules, NAT, load balancing, IAM, storage)",
             hint="Each failing line names the original requirement; its hint in that lesson says what to fix")
def phase2(plan):
    baseline.require_all(plan, PHASE2)


@requirement("R24.3", "Phase 3 baselines still hold (lessons 12-17: data, serverless, events, GKE, CI identities, observability)",
             hint="Keep one workflow file: lesson 16's checks still read it")
def phase3(plan):
    baseline.require_all(plan, PHASE3)


@requirement("R24.4", "Phase 4 baselines still hold (lessons 18-23: hybrid network, security, HA, DR, landing zone)",
             hint="A later lesson can break an earlier guarantee: read which requirement fails and why")
def phase4(plan):
    baseline.require_all(plan, PHASE4)


@requirement("R24.5", "CI covers every root and promotes dev before prod, behind environments",
             hint="Static checks validate envs/dev, prod, hub, platform and bootstrap; PR plans for the four envs; "
                  "an apply per env root on main behind its own environment; the prod apply needs the dev apply")
def pipeline(plan):
    wf = _wf(plan)
    static = [j for j in wf.jobs if "fmt -check" in j.runs()]
    require(static, "No static-checks job (terraform fmt -check)")
    missing = [r for r in ALL_ROOTS if r not in _roots(static[0], "validate")]
    require(not missing, f"{static[0].id} doesn't validate {missing}")

    pr = _pr_plan_jobs(wf)
    require(pr, "No job plans on pull requests (if: github.event_name == 'pull_request')")
    planned = set().union(*(_roots(j, "plan") for j in pr))
    missing = [f"envs/{r}" for r in ENV_ROOTS if f"envs/{r}" not in planned]
    require(not missing, f"Pull requests don't plan {missing} - reviewers would merge changes to them blind")
    plan_sas = {_sa(j) for j in pr}

    problems = []
    for r in ENV_ROOTS:
        root = f"envs/{r}"
        jobs = _apply_jobs(wf, root)
        if not jobs:
            problems.append(f"nothing applies {root}")
            continue
        for j in jobs:
            if "refs/heads/main" not in j.condition:
                problems.append(f"{j.id} applies {root} without `if:` restricting it to main")
            env = _environment(j, root)
            if not env:
                problems.append(f"{j.id} applies {root} with no environment")
            elif r == "prod" and env.lower() not in ("prod", "production"):
                problems.append(f"{j.id} applies prod in environment {env!r} - prod needs its own (prod), with its own reviewers")
            if not any(s.id in _needs_all(wf, j) for s in static):
                problems.append(f"{j.id} doesn't wait for the static checks")
            if _sa(j) and _sa(j) in plan_sas:
                problems.append(f"{j.id} applies with the read-only plan identity")
    dev_jobs = {j.id for j in _apply_jobs(wf, "envs/dev")}
    for j in _apply_jobs(wf, "envs/prod"):
        if dev_jobs and not (dev_jobs & _needs_all(wf, j)):
            problems.append(f"{j.id} doesn't need the dev apply ({', '.join(sorted(dev_jobs))}) - prod could change before dev proved the change")
    require(not problems, "\n  ".join(problems))


@requirement("R24.6", "The platform modules have their own tests",
             hint="modules/<landing-zone|project-factory|central-logging>/tests/*.tftest.hcl: mock_provider, 2+ runs, 3+ assertions; "
                  "central-logging asserts include_children; project-factory tests a validation with expect_failures")
def platform_tests(plan):
    problems = []
    for m in PLATFORM_MODULES:
        files = plan.source.test_files(f"modules/{m}/tests")
        if not files:
            problems.append(f"modules/{m}: no tests/*.tftest.hcl")
            continue
        blocks = [b for bl in files.values() for b in bl]
        runs = [b for b in blocks if b.type == "run"]
        checks_ = sum(len(r.blocks("assert")) + (1 if r.attr("expect_failures") else 0) for r in runs)
        if not any(b.type == "mock_provider" for b in blocks):
            problems.append(f"modules/{m}: no mock_provider - tests must run without credentials")
        if len(runs) < 2 or checks_ < 3:
            problems.append(f"modules/{m}: {len(runs)} run block(s), {checks_} assertion(s) - write at least 2 and 3")
        text = "\n".join(plan.source.files[f] for f in files)
        if m == "central-logging" and "include_children" not in text:
            problems.append("modules/central-logging: no test asserts include_children (lesson 23's silent failure)")
        if m == "project-factory" and not any(r.attr("expect_failures") for r in runs):
            problems.append("modules/project-factory: no run checks that bad input is rejected (expect_failures)")
    require(not problems, "\n  ".join(problems))


@requirement("R24.7", "docs/architecture.md explains the roots and draws every major component",
             hint="A ```mermaid diagram naming dev, prod, hub, platform and bootstrap, both regions, and each component the plans build "
                  "(load balancer, Cloud Armor, MIG, Cloud Run, Cloud SQL, GKE, Pub/Sub, registry, KMS, VPN, DNS, folders, log sink, Shared VPC)")
def architecture(plan):
    spec = RUBRIC["architecture"]
    text = _doc(plan, spec["file"], "describe the platform there")
    diagrams = docs.fenced(text, "mermaid")
    require(diagrams, f"{spec['file']} has no ```mermaid diagram")
    diagram = "\n".join(diagrams).lower()
    plans = [plan] + list(plan.others.values())
    missing = [r for r in ["dev", "prod", "hub", "platform", "bootstrap"] if not re.search(rf"\b{r}\b", diagram)]
    regions = sorted({str(p.variable_value(v)) for p in plans for v in ("region", "dr_region") if p.variable_value(v)})
    missing += [r for r in regions if r not in diagram]
    types = set().union(*(p.types() for p in plans))
    for rtype, words in spec["components"].items():
        if rtype in types and not any(wd in diagram for wd in words):
            missing.append(f"{words[0]} ({rtype})")
    require(not missing, "The diagram doesn't show:\n  " + "\n  ".join(missing))
    require(docs.words(text) >= 80, f"{spec['file']} has {docs.words(text)} words outside the diagram - explain the roots and the request path")


@requirement("R24.8", "Architecture decision records explain the big choices",
             hint="docs/adr/NNNN-title.md, at least 3, each with Status:, Context, Decision, Alternatives considered and Consequences; "
                  "together covering the landing zone, the network topology and disaster recovery")
def adrs(plan):
    spec = RUBRIC["adr"]
    prefix = spec["dir"].rstrip("/") + "/"
    records = {p: t for p, t in plan.source.docs.items()
               if p.startswith(prefix) and re.match(spec["name_pattern"], p[len(prefix):]) and not p[len(prefix):].startswith("0000")}
    require(len(records) >= spec["min_records"],
            f"{len(records)} decision record(s) in {prefix} named NNNN-title.md - write at least {spec['min_records']}")
    nums = [p[len(prefix):][:4] for p in records]
    dupes = sorted({n for n in nums if nums.count(n) > 1})
    require(not dupes, f"ADR numbers used twice: {dupes}")
    problems = [f"{p}: {'; '.join(probs)}" for p, t in sorted(records.items()) if (probs := docs.check_record(t, spec))]
    require(not problems, "\n  ".join(problems))
    covered = docs.topics_covered(list(records.values()), spec["topics"])
    missing = [t for t, ok in covered.items() if not ok]
    require(not missing, f"No decision record covers: {missing}")


@requirement("R24.9", "The zone-loss analysis in docs/failure-analysis.md matches the prod plan",
             hint="A table with Workload, Minimum capacity and After losing a zone columns: one row per prod workload (MIGs, Cloud SQL "
                  "instances, GKE) with the numbers coursekit.failure computes - EVEN spread loses ceil(n/zones)")
def zone_analysis(plan):
    prod = plan.others["prod"]
    text = _doc(plan, "docs/failure-analysis.md", "write the failure analysis there")
    found = docs.find_table(text, r"workload", r"min", r"after|left|remain")
    require(found, "No table with Workload, Minimum capacity and After losing a zone columns")
    rows, (c_wl, c_min, c_after) = found
    loads = failure.workloads(prod)
    worst = failure.worst_case(prod)
    seen, problems = set(), []
    for row in rows:
        hits = _match_workload(row[c_wl], loads)
        if len(hits) != 1:
            problems.append(f"row {row[c_wl]!r} matches {len(hits)} prod workloads - use the resource address")
            continue
        w = hits[0]
        seen.add(w.address)
        lo, after = docs.number(row[c_min]), docs.number(row[c_after])
        if lo != w.min_capacity:
            problems.append(f"{w.address}: minimum capacity is {w.min_capacity}, the table says {row[c_min]!r}")
        if after != worst[w.address][0]:
            problems.append(f"{w.address}: {worst[w.address][0]} left after losing {worst[w.address][1]}, the table says {row[c_after]!r}")
    problems += [f"{a}: no row" for a in sorted(worst) if a not in seen]
    require(not problems, "The analysis doesn't match the plan:\n  " + "\n  ".join(problems))


@requirement("R24.10", "Deployed dev doesn't change",
             hint="The capstone proves the platform; dev's plan shows no changes (prod-only fixes are fine)")
def dev_unchanged(plan):
    changed = [f"{r.address} ({'/'.join(r.actions)})" for r in plan.all_changes() if r.actions not in (["no-op"], ["read"])]
    require(not changed, "dev would change:\n  " + "\n  ".join(changed[:15]))


# ------------------------------------------------------------------ challenge
@requirement("C24.1", "A self-assessment scores every rubric criterion, with evidence that exists",
             hint="docs/self-assessment.md: | Criterion | Score (1-4) | Evidence | - one row per criterion in rubric.json, "
                  "evidence = paths of files in the repository", level="challenge")
def self_assessment(plan):
    text = _doc(plan, "docs/self-assessment.md", "score yourself against the rubric")
    found = docs.find_table(text, r"criteri", r"score", r"evidence")
    require(found, "No table with Criterion, Score and Evidence columns")
    rows, (c_crit, c_score, c_ev) = found
    by_name = {r[c_crit].strip().lower(): r for r in rows}
    problems = []
    paths_ = plan.source.paths
    for crit in RUBRIC["criteria"]:
        row = by_name.get(crit["name"].lower())
        if row is None:
            problems.append(f"{crit['name']}: no row")
            continue
        score = docs.number(row[c_score])
        if score is None or score != int(score) or not 1 <= score <= 4:
            problems.append(f"{crit['name']}: score {row[c_score]!r} - use 1 to 4")
        cited = re.findall(r"[\w.-]+(?:/[\w.-]+)+|[\w-]+\.(?:md|tf|tfvars|yml|yaml|hcl|json)\b", row[c_ev])
        exists = lambda p: p.rstrip("/") in paths_ or any(x.startswith(p.rstrip("/") + "/") for x in paths_)
        bad = [p for p in cited if not exists(p)]
        if not cited:
            problems.append(f"{crit['name']}: no evidence - cite files in the repository")
        elif bad:
            problems.append(f"{crit['name']}: evidence not found: {bad}")
    require(not problems, "\n  ".join(problems))


@requirement("C24.2", "The region-loss analysis matches the plan and the recovery objectives",
             hint="docs/failure-analysis.md: | Data store | RPO target | RPO if <region> is lost | Meets target | - rows database, backups, images",
             level="challenge")
def region_analysis(plan):
    prod = plan.others["prod"]
    text = _doc(plan, "docs/failure-analysis.md", "add the region-loss analysis there")
    found = docs.find_table(text, r"data|store", r"target", r"lost|loss", r"meet")
    require(found, "No table with Data store, RPO target, RPO if the region is lost and Meets target columns")
    rows, (c_store, c_target, c_rpo, c_meets) = found
    objectives = prod.variable_value("recovery_objectives") or {}
    stores = failure.data_stores(prod)
    by_name = {r[c_store].strip().lower(): r for r in rows}
    problems = []
    for name, pred in OBJECTIVE_STORES.items():
        row = by_name.get(name)
        store = next((s for s in stores if pred(s)), None)
        if row is None or store is None or name not in objectives:
            problems.append(f"{name}: no row" if row is None else f"{name}: nothing to compare (objective or data store missing)")
            continue
        target = objectives[name]["rpo_minutes"]
        rpo = store.rpo_minutes
        if docs.number(row[c_target]) != target:
            problems.append(f"{name}: the agreed RPO target is {target} min, the table says {row[c_target]!r}")
        if rpo >= failure.UNLIMITED:
            if docs.number(row[c_rpo]) is not None:
                problems.append(f"{name}: all data is lost with the region, the table says {row[c_rpo]!r}")
        elif docs.number(row[c_rpo]) != rpo:
            problems.append(f"{name}: losing the region loses {rpo} min of data, the table says {row[c_rpo]!r}")
        meets = row[c_meets].strip().lower()
        expected = rpo <= target
        if meets.startswith(("yes", "y", "true", "met")) != expected or (not expected and not meets.startswith(("no", "n", "false", "miss"))):
            problems.append(f"{name}: meets target should be {'yes' if expected else 'no'}, the table says {row[c_meets]!r}")
    require(not problems, "\n  ".join(problems))


@requirement("C24.3", "A scheduled job detects drift in every environment root",
             hint="on: schedule: - cron: ...; a job with if: github.event_name == 'schedule' running "
                  "plan -detailed-exitcode in envs/dev, prod, hub and platform with the read-only plan identity", level="challenge")
def drift(plan):
    wf = _wf(plan)
    sched = wf.triggers.get("schedule")
    require(isinstance(sched, list) and any(isinstance(s, dict) and s.get("cron") for s in sched), "The workflow has no schedule trigger with a cron")
    jobs = [j for j in wf.jobs if "schedule" in j.condition and any("-detailed-exitcode" in l for l in _tf_lines(j, "plan"))]
    require(jobs, "No job runs `terraform plan -detailed-exitcode` on the schedule")
    covered = set().union(*(_roots(j, "plan") for j in jobs))
    missing = [f"envs/{r}" for r in ENV_ROOTS if f"envs/{r}" not in covered]
    require(not missing, f"Drift detection skips {missing}")
    apply_sas = {_sa(j) for r in ENV_ROOTS for j in _apply_jobs(wf, f"envs/{r}")} - {""}
    bad = [j.id for j in jobs if _tf_lines(j, "apply") or (_sa(j) and _sa(j) in apply_sas)]
    require(not bad, f"{bad}: drift detection must only read - use the plan identity, never apply")


@requirement("C24.4", "prod applies exactly the plan that was reviewed",
             hint="A job plans envs/prod with -out=tfplan and uploads it (actions/upload-artifact); the prod apply job needs it, "
                  "downloads it (actions/download-artifact) and runs `terraform apply tfplan` - no new plan", level="challenge")
def reviewed_plan(plan):
    wf = _wf(plan)
    jobs = _apply_jobs(wf, "envs/prod")
    require(len(jobs) == 1, f"Expected one job that applies envs/prod, found {[j.id for j in jobs]}")
    j = jobs[0]
    require(j.uses_action("actions/download-artifact"), f"{j.id} doesn't download a saved plan (actions/download-artifact)")
    require(not _tf_lines(j, "plan"), f"{j.id} plans again - it must apply the file that was reviewed")
    applies = _tf_lines(j, "apply")
    require(all(re.search(r"\bapply\b(?:\s+-\S+)*\s+[^\s-]\S*\s*$", l) for l in applies),
            f"{j.id} must apply a plan file: `terraform -chdir=envs/prod apply tfplan`")
    require(all("-auto-approve" not in l for l in applies), f"{j.id}: -auto-approve isn't needed when applying a saved plan - drop it so a missing file can't turn into a fresh apply")
    makers = [wf.job(n) for n in _needs_all(wf, j) if wf.job(n) is not None]
    makers = [m for m in makers if "envs/prod" in _roots(m, "plan") and any("-out" in l for l in _tf_lines(m, "plan"))]
    require(makers, f"None of the jobs {j.id} needs plans envs/prod with -out")
    require(any(m.uses_action("actions/upload-artifact") for m in makers), f"{makers[0].id} doesn't upload its plan (actions/upload-artifact)")
