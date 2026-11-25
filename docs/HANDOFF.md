# Handoff notes (state as of lesson 24 - course complete)

Working notes for whoever continues building the course: a person or an AI session.
Read with [AUTHORING.md](AUTHORING.md), [VALIDATION.md](VALIDATION.md) and [ROADMAP.md](ROADMAP.md).

## Where things stand

- All lessons **01–24 are ready** (24 = capstone). ROADMAP.md lists candidate next steps.
- GitHub (public beta): `main` there is a fresh history that starts from one commit of `course-menu`; it is
  kept locally as `github-main`. Push only `github-main:main`. The local branches below have a separate history and stay local.
- Git (local): `main` = initial commit (lessons 01–11).
  Each later lesson is on its own branch, **stacked** on the previous one:
  `lesson-12-databases` → `lesson-13-serverless` → … → `lesson-19-security` → `lesson-20-advanced-terraform` → `lesson-21-high-availability` → `lesson-22-disaster-recovery` → `lesson-23-enterprise-platform` → `lesson-24-capstone`
  → `course-menu` (current, contains everything). Merging the latest branch into `main` (fast-forward) brings all of it in.
- Every lesson's self-test passed when it was committed. Self-test runs on GitHub on pushes to main.

## How each lesson was built (the recipe)

1. `git switch -c lesson-NN-<slug>` from the previous lesson branch.
2. **Generator script** (kept outside the repo) that copies the previous lesson's `solution/` and applies
   edits with exact-string `sub()` calls, then writes `solution/`, `solution-challenge/` and `starter/`
   (= previous solution + TODO stub files). Run `terraform fmt -recursive` on the lesson afterwards.
3. Deployed state for dev, generated from the previous solution:
   `python -m coursekit.statefab lessons/<prev>/solution lessons/<NN>/state/dev.tfstate envs/dev`,
   then copy it to `starter/state/dev.tfstate`. (Lesson 10 uses `"state_from": "starter"` because its
   deployed state includes the audited legacy file.)
4. `lesson.json` with `roots` (dev first; lesson 18+ adds `"hub": "envs/hub"`, lesson 23+ `"platform": "envs/platform"`) and `state`.
5. Plan both solutions with `python course.py check NN --path lessons/NN/solution -v` and look at the
   dev plan shape (`N to add, M to change, 0 to destroy`). Design so dev changes are additions or
   in-place updates; deletions only when intended (and the "safe change" requirement allows that type).
6. `checks.py`: 10 lab (RNN.x) + 4 challenge (CNN.x) requirements. One requirement is always the
   "deployed dev changes safely" guard rail; another usually checks prod mirrors dev.
7. A module test for the challenge (C*.4): `tests/challenge/*.tftest.hcl` runs in the dev root;
   modules with `configuration_aliases` put it in `tests/challenge/modules/<module>/` instead (runs in the module dir).
8. Fixtures generator: one `bad-*` per requirement (files overlaid on a solution + `expect.json`),
   plus `broken/` (one realistic fault, README + ANSWER). Then `python course.py selftest NN --workers 8`.
   Self-test regularly finds lenient checks or fixtures that break validation instead of the requirement:
   fix the check or the fixture; never weaken the expectation silently.
9. Docs: README (story, objectives, concepts, how it's checked, mermaid, lab files, costs), lab.md,
   challenge.md, broken README/ANSWER. Update README course map, ROADMAP ("Done in lesson NN" + "Next up").
10. Regression: if coursekit changed, re-run self-tests of lessons using the touched code
    (in chunks: one call must finish within ~10 minutes). Unit tests: `python -m unittest discover -s tests -t .`
11. Clean `.course/build` and `workspace/0*`/`workspace/1*`, then commit with the attribution trailer.

## Tooling added along the way (coursekit)

| Module | Purpose |
|---|---|
| `plan.py` | Plan model; `linked()` follows refs across modules (`expand_ref`), keyed outputs, `module_input_resources` |
| `firewall.py` | VPC firewall + Cloud NAT egress + PGA + internal sources (`internal_ip`) |
| `lb.py` | Load balancer tracing (incl. MIG backends, dynamic backends via module inputs) |
| `iam.py` | Effective grants: project, SA, bucket, secret, repository, Cloud Run, topic, subscription, KMS key |
| `hcl.py` | HCL source reader (lifecycle, backends, one-line blocks), `.tfvars`, `.tftest.hcl`, workflows |
| `workflow.py` | Stdlib YAML-subset reader for GitHub Actions |
| `statefab.py` | Deployed-state fabricator with realistic IDs / attribute templates (`_ID_TEMPLATES`, `_ATTR_TEMPLATES`) |
| `cloudsim.py` | Offline `import` blocks: inventory of hand-made objects -> injected into prepared state |
| `failure.py` | Failure-domain analyser: zone loss (capacity per workload) and region loss (data stores, RPO) |
| `baseline.py` | Re-run earlier lessons' requirements by ID (capstone baselines) |
| `docs.py` | Markdown reader + rubric checks (ADRs, diagrams, tables compared with the plan) |
| `app/` | The course app (`python course.py`): stdlib HTTP server on 127.0.0.1 (`server.py`), markdown renderer, Monaco cache (`vendor.py`, filled by `setup`, CDN/plain fallback), in-app updates (`update.py`: fast-forward only, restarts in a new process; hidden unless the clone tracks a remote branch), static UI. Reuses `guide.tasks`/progress and `runner.check` |
| `guide.py` | Guided mode (`python course.py`): lesson intro → lab → challenge → troubleshooting → next lesson, progress in `workspace/.progress.json`; `check-all` batch checks |
| `runner.py` | Multi-root plans, prepared state, lesson tests, module tests (`modules/*/tests`), module-scoped lesson tests |

## Pitfalls learned (Windows)

- Bash heredocs mangle backslashes and quotes: write Python patch/generator scripts to files and run them.
  In HCL regexes avoid backslashes, e.g. `[.]` instead of `\.`.
- Windows MAX_PATH: build dirs use short names (`.course/build/19l`).
- Files written by Python on Windows get CRLF; git normalizes to LF (`.gitattributes`).
  Write with `newline="\n"` where possible.
- `cidrcontains` doesn't exist in this Terraform version; regex instead.
- Provider defaults hide missing settings (e.g. backend draining 300s, scheduler time zone UTC):
  checks must require explicit values, not "is set".
- Terraform infers the `x` -> `x[0]` move when `count` is added; renames and `for_each` keys need `moved`.
- statefab runs plans in rounds; `prevent_destroy` is stripped in its temp copy (L19 KMS key broke it).
- `prevent_destroy` doesn't protect a resource whose block is deleted: use `removed { lifecycle { destroy = false } }`.
- Passing `null` explicitly to a module input ignores its default; module defaults only apply when the argument is omitted.
- An `import` block whose address is already in state is skipped without comparing IDs (basis of cloudsim).
- `.devcontainer/` isn't copied when the app moves a session folder; it was recreated by hand.
- A later lesson can silently break an earlier requirement (L22's zonal replica broke R21.5); the capstone
  baselines exist for that. When changing an old lesson's behaviour, run `selftest 24` too.
- Markdown table cells: strip code ticks and surrounding bold markers only, never underscores (resource addresses).
