"""Lesson 16 - CI/CD and Terraform Automation.

`plan` is dev against the deployed lesson 15 environment. The workflow is read
from .github/workflows/*.yml with coursekit.workflow (no YAML package needed),
and student-written module tests run as their own stage.
"""

import re

from coursekit import iam
from coursekit.checks import require, requirement
from coursekit.workflow import YamlError

READ_ONLY = re.compile(r"(viewer|Viewer|\.reader|securityReviewer|serviceUsageViewer|roleViewer)$")
SHA_PIN = re.compile(r"^[^@]+@[0-9a-f]{40}$")
AUTH = "google-github-actions/auth"


def _wf(plan):
    try:
        wfs = plan.source.workflows()
    except YamlError as exc:
        require(False, f"Workflow file can't be parsed: {exc}")
    wfs = [w for w in wfs if w.jobs]
    require(wfs, "No GitHub Actions workflow with jobs in .github/workflows/")
    require(len(wfs) == 1, f"Expected one Terraform workflow, found {[w.path for w in wfs]}")
    return wfs[0]


def _job_with(wf, needle):
    return [j for j in wf.jobs if needle in j.runs()]


def _plan_job(wf):
    jobs = [j for j in wf.jobs if re.search(r"terraform\b.*\bplan\b", j.runs())]
    require(len(jobs) == 1, f"Expected one job that runs terraform plan, found {[j.id for j in jobs]}")
    return jobs[0]


def _apply_job(wf):
    jobs = [j for j in wf.jobs if re.search(r"terraform\b.*\bapply\b", j.runs())]
    require(len(jobs) == 1, f"Expected one job that runs terraform apply, found {[j.id for j in jobs]}")
    return jobs[0]


def _sa(plan, account_id):
    s = [x for x in plan.resources("google_service_account") if x.get("account_id") == account_id]
    require(s, f"Service account {account_id} not found")
    return s[0]


def _member_text(plan, res):
    """The member value, or its HCL expression when only known after apply."""
    val = res.get("member")
    if isinstance(val, str):
        return val
    name = res.address.split(".")[-1].split("[")[0]
    for blk in plan.source.blocks("resource", res.type, name):
        return blk.attr("member") or ""
    return ""


def _wiu_on(plan, sa):
    return [g for g in iam.grants(plan) if g.scope == "service_account" and g.role == "roles/iam.workloadIdentityUser"
            and g.target is not None and g.target.address == sa.address]


# ------------------------------------------------------------------ lab
@requirement("R16.1", "GitHub Actions can authenticate keylessly - from one repository only",
             hint="Workload identity pool + OIDC provider (token.actions.githubusercontent.com) mapping attribute.repository and attribute.ref, "
                  "attribute_condition = \"assertion.repository == 'owner/repo'\"")
def oidc(plan):
    providers = plan.resources("google_iam_workload_identity_pool_provider")
    require(len(providers) == 1, f"Expected one workload identity pool provider, found {len(providers)}")
    p = providers[0]
    require(p.get("oidc.0.issuer_uri") == "https://token.actions.githubusercontent.com", "The provider must trust GitHub's OIDC issuer")
    mapping = p.get("attribute_mapping") or {}
    for attr in ("google.subject", "attribute.repository", "attribute.ref"):
        require(attr in mapping, f"attribute_mapping is missing {attr}")
    cond = p.get("attribute_condition") or ""
    require("assertion.repository" in cond and "==" in cond,
            "attribute_condition must pin the repository - otherwise any GitHub repository can use this pool")


@requirement("R16.2", "Pull-request plans use a read-only identity",
             hint="meridian-ci-plan: only *viewer / *reader / securityReviewer roles; workloadIdentityUser for principalSet .../attribute.repository/<repo>")
def plan_identity(plan):
    sa = _sa(plan, "meridian-ci-plan")
    roles = sorted(g.role for g in iam.for_principal(iam.grants(plan), f"sa:{sa.address}", "project"))
    require(len(roles) >= 3, f"The plan identity has {roles or 'no roles'} - it needs read access to plan")
    writes = [r for r in roles if not READ_ONLY.search(r) or r in iam.BASIC_ROLES]
    require(not writes, f"The plan identity can change things: {writes}")
    wiu = _wiu_on(plan, sa)
    require(wiu, "No workloadIdentityUser binding: GitHub can't act as the plan identity")
    texts = [_member_text(plan, g.source) for g in wiu]
    require(all("attribute.repository/" in t for t in texts), f"Bind the plan identity to the repository principalSet, found {texts}")
    require(not plan.resources("google_service_account_key"), "No service account keys")


@requirement("R16.3", "Only workflows on main can act as the apply identity",
             hint="workloadIdentityUser on meridian-ci for principalSet://iam.googleapis.com/<pool>/attribute.ref/refs/heads/main")
def apply_identity(plan):
    sa = _sa(plan, "meridian-ci")
    wiu = _wiu_on(plan, sa)
    require(wiu, "GitHub can't act as meridian-ci - the apply job would have no identity")
    texts = [_member_text(plan, g.source) for g in wiu]
    require(all("attribute.ref/refs/heads/main" in t for t in texts),
            f"meridian-ci must be restricted to refs/heads/main, found {texts} - any branch or PR could apply")


@requirement("R16.4", "The pipeline runs on pull requests and on pushes to main",
             hint="on: { pull_request: { branches: [main] }, push: { branches: [main] } }")
def triggers(plan):
    t = _wf(plan).triggers
    require("pull_request" in t, "The workflow doesn't run on pull requests")
    push = t.get("push") or {}
    require("push" in t and "main" in (push.get("branches") or []), "The workflow doesn't run on pushes to main")
    require("pull_request_target" not in t, "pull_request_target runs untrusted PR code with secrets - use pull_request")


@requirement("R16.5", "Static checks run with no cloud credentials",
             hint="A job that runs terraform fmt -check, validate (every root) and terraform test - and has no auth step or id-token permission")
def static_checks(plan):
    wf = _wf(plan)
    jobs = [j for j in wf.jobs if "fmt -check" in j.runs()]
    require(jobs, "No job runs terraform fmt -check")
    j = jobs[0]
    runs = j.runs()
    require("validate" in runs, f"{j.id} doesn't run terraform validate")
    require(re.search(r"terraform\b.*\btest\b", runs), f"{j.id} doesn't run terraform test")
    require("-backend=false" in runs, f"{j.id} should init with -backend=false - static checks need no state access")
    require(not j.uses_action(AUTH), f"{j.id} authenticates to Google Cloud - static checks need no credentials")
    perms = j.permissions or {}
    require(not (isinstance(perms, dict) and perms.get("id-token") == "write"), f"{j.id} doesn't need id-token: write")


@requirement("R16.6", "PR plans authenticate keylessly with the plan identity",
             hint="plan job: permissions { id-token: write }, google-github-actions/auth with workload_identity_provider + service_account, plan -lock=false")
def plan_job(plan):
    wf = _wf(plan)
    j = _plan_job(wf)
    text = "\n".join(f"{s.with_}" for jj in wf.jobs for s in jj.steps)
    require("credentials_json" not in text, "A step uses credentials_json - that's a service account key in a GitHub secret")
    perms = j.permissions if isinstance(j.permissions, dict) else {}
    require(perms.get("id-token") == "write", f"{j.id} needs permissions: id-token: write to request a GitHub OIDC token")
    auth = j.uses_action(AUTH)
    require(auth, f"{j.id} has no {AUTH} step")
    w = auth[0].with_
    require(w.get("workload_identity_provider") and w.get("service_account"),
            "The auth step needs workload_identity_provider and service_account")
    require("PLAN" in str(w.get("service_account")).upper() or "plan" in str(w.get("service_account")),
            f"The plan job should use the plan identity, got {w.get('service_account')}")
    require("-lock=false" in j.runs() or "-lock-timeout" in j.runs(),
            "PR plans run in parallel with each other: use -lock=false (read-only) so they don't fight over the state lock")
    require("pull_request" in j.condition or set(wf.triggers) == {"pull_request"},
            f"{j.id} should only run for pull requests (if: github.event_name == 'pull_request')")


@requirement("R16.7", "Apply runs only for main, after the checks, behind an environment",
             hint="apply job: if: github.event_name == 'push' && github.ref == 'refs/heads/main', needs: <checks job>, environment: dev, apply identity")
def apply_job(plan):
    wf = _wf(plan)
    j = _apply_job(wf)
    require("refs/heads/main" in j.condition, f"{j.id} has no `if:` restricting it to main - every pull request would apply to dev")
    require("push" in j.condition or "pull_request" not in wf.triggers, f"{j.id} should only run on push events")
    checks = [x.id for x in wf.jobs if "fmt -check" in x.runs()]
    require(any(c in j.needs for c in checks), f"{j.id} must need the static checks job {checks}")
    require(j.environment, f"{j.id} has no environment - add one so you can require approval and scope secrets")
    auth = j.uses_action(AUTH)
    require(auth, f"{j.id} has no {AUTH} step")
    plan_sa = str(_plan_job(wf).uses_action(AUTH)[0].with_.get("service_account") if _plan_job(wf).uses_action(AUTH) else "")
    require(str(auth[0].with_.get("service_account")) != plan_sa, "Apply must use a different identity than plan")


@requirement("R16.8", "The workflow's default token is read-only",
             hint="top-level permissions: { contents: read } - grant id-token: write only on the jobs that authenticate")
def default_permissions(plan):
    perms = _wf(plan).permissions
    require(perms is not None, "No top-level permissions: GITHUB_TOKEN may get write access to the repository by default")
    if isinstance(perms, dict):
        writes = [k for k, v in perms.items() if v == "write"]
        require(not writes, f"Top-level permissions grant write: {writes}")
    else:
        require(perms in ("read-all", {}), f"Top-level permissions {perms!r}: use contents: read")


@requirement("R16.9", "Your modules have their own tests",
             hint="modules/<name>/tests/*.tftest.hcl with mock_provider, at least 3 run blocks and 5 assertions in total")
def module_tests(plan):
    files = plan.source.test_files("modules")
    require(files, "No .tftest.hcl files under modules/*/tests/")
    runs = asserts = 0
    mocked = False
    for blocks in files.values():
        for b in blocks:
            if b.type == "run":
                runs += 1
                asserts += len(b.blocks("assert"))
            if b.type == "mock_provider":
                mocked = True
    require(mocked, "Use mock_provider so tests need no credentials")
    require(runs >= 3, f"{runs} run blocks - write at least 3")
    require(asserts >= 5, f"{asserts} assertions - write at least 5")


@requirement("R16.10", "Deployed dev changes safely; prod gets the same identities",
             hint="Additions only. prod calls the same modules.")
def safe(plan):
    bad = []
    for r in plan.all_changes():
        if r.is_replaced:
            bad.append(f"{r.address} would be REPLACED")
        elif r.actions == ["delete"]:
            bad.append(f"{r.address} would be DESTROYED")
    require(not bad, "Against the deployed dev environment:\n  " + "\n  ".join(bad))
    srcs = lambda p: {n: c.get("source") for n, c in p.configuration.get("root_module", {}).get("module_calls", {}).items()}
    require(srcs(plan) == srcs(plan.others["prod"]), "dev and prod call different modules")


# ------------------------------------------------------------------ challenge
@requirement("C16.1", "Every action is pinned to a full commit SHA",
             hint="uses: actions/checkout@<40-character SHA> # v4", level="challenge")
def pinned(plan):
    loose = sorted({s.uses for j in _wf(plan).jobs for s in j.steps if s.uses and not SHA_PIN.match(s.uses)})
    require(not loose, f"Actions pinned by tag (a tag can be moved to malicious code): {loose}")


@requirement("C16.2", "Runs for the same ref never overlap, and applies are never cancelled",
             hint="concurrency: { group: terraform-${{ github.ref }}, cancel-in-progress: false }", level="challenge")
def concurrency(plan):
    wf = _wf(plan)
    c = wf.data.get("concurrency") or _apply_job(wf).data.get("concurrency")
    require(c, "No concurrency group: two pushes to main could apply at the same time")
    if isinstance(c, dict):
        require(c.get("cancel-in-progress") is not True, "cancel-in-progress: true could kill an apply halfway through")


@requirement("C16.3", "The checks job lints the code",
             hint="Run tflint (or checkov / trivy) in the static checks job", level="challenge")
def lint(plan):
    wf = _wf(plan)
    j = [x for x in wf.jobs if "fmt -check" in x.runs()][0]
    require(re.search(r"\b(tflint|checkov|trivy|conftest)\b", j.runs()), f"{j.id} runs no linter")


@requirement("C16.4", "Reviewers can read the plan",
             hint="terraform show tfplan > plan.txt + actions/upload-artifact (or a PR comment)", level="challenge")
def plan_artifact(plan):
    j = _plan_job(_wf(plan))
    require(j.uses_action("actions/upload-artifact") or j.uses_action("actions/github-script"),
            f"{j.id} doesn't publish the plan for review")
