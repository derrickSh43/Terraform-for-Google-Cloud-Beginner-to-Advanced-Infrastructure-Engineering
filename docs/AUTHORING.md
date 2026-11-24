# Authoring a lesson

Lessons 06–24 are outlined in their `README.md`. To publish one, build the
pieces below, then flip `"status"` to `"ready"` in `lesson.json`.

## Folder layout

```
lessons/NN-slug/
├── lesson.json            {"id", "slug", "title", "phase", "status", "project"}
├── README.md              concepts · mermaid architecture · lab file table · "if this were real" costs
├── lab.md                 guided steps, each naming its requirement IDs (RNN.x)
├── challenge.md           CNN.x requirements as a table, hints, "think about it"
├── checks.py              @requirement functions (lab + challenge)
├── starter/               = previous lesson's solution + new files containing TODOs
├── solution/              passes every lab requirement
├── solution-challenge/    passes lab + challenge
├── tests/lab/*.tftest.hcl          optional native tests (use mock_provider)
├── tests/challenge/*.tftest.hcl
├── fixtures/<bad-name>/   files overlaid on a solution + expect.json
└── broken/                full config with ONE planted fault + README.md + ANSWER.md + expect.json
```

## Step by step

1. **Write the solution first.** Start from the previous lesson's `solution/`
   (project lessons) and add the new infrastructure. Run `terraform fmt -recursive`.
2. **Derive the starter.** Copy the previous solution and add the new files as
   TODO stubs that name requirement IDs. The starter must pass fmt and validate.
3. **Write `checks.py`.** One `@requirement` per learning objective. Aim for 6–10
   lab requirements and 3–5 challenge requirements. See [VALIDATION.md](VALIDATION.md#writing-robust-checks).
   ```python
   from coursekit.checks import one, require, requirement

   @requirement("R6.1", "Short student-facing title", hint="the fix, in one line")
   def something(plan):
       res = one(plan, "google_compute_router")
       require(res.get("bgp.0.asn"), "Cloud Router has no BGP ASN")
   ```
4. **Add fixtures.** At least one per requirement (or per pair of closely related ones):
   ```json
   {"fail_ids": ["R6.1"]}
   {"base": "solution-challenge", "level": "challenge", "fail_ids": ["C6.2"]}
   {"fail_stage": "validate"}
   ```
   A fixture folder holds only the files that differ from its base. Add
   `"delete": ["file.tf"]` to remove a file.
5. **Write the broken repo.** One realistic fault, shown through a symptom
   ("the API times out"). Vary the failure stage across lessons: validate (01, 02),
   a requirement that passes plan (03, 04), connectivity (05).
6. **Write the docs.** Use the same section order as lessons 01–05.
7. **Self-test.**
   ```powershell
   python course.py selftest 06
   ```
   Then set `"status": "ready"` and run the full `python course.py selftest`.

## Definition of done

- [ ] `selftest NN` passes (solutions pass; every fixture and the broken repo fail as declared)
- [ ] Every requirement has at least one fixture that fails it
- [ ] Starter = previous solution + TODO stubs (enforced by selftest)
- [ ] Architecture diagram (mermaid) renders on GitHub
- [ ] README has an "If this were real" cost note
- [ ] No data sources that call live GCP APIs
- [ ] Student-facing messages say what was found and what was expected

## Multi-root lessons and deployed state (lesson 06 onward)

`lesson.json` can declare several root modules and a prepared state:

```json
{
  "roots": {"dev": "envs/dev", "prod": "envs/prod", "bootstrap": "bootstrap"},
  "state": {"dev": "state/dev.tfstate"},
  "starter_previous": "legacy"
}
```

- The **first** root is the primary: checks receive its plan, and siblings are in `plan.others["prod"]`.
- `state` maps a root to a state file that is copied in as that root's local state, so the
  plan is computed **against a deployed environment**. Generate it from any configuration:
  ```powershell
  python -m coursekit.statefab lessons/05-networking-firewalls/solution lessons/06-terraform-state-modules/state/dev.tfstate
  ```
  It plans offline, fills "known after apply" values with schema-typed fakes, and iterates
  until planning that config against the state shows **no changes**.
- `starter_previous`: the starter keeps the previous solution in this subfolder (e.g. `legacy/`)
  instead of at the root. `selftest` and `start --from-mine` both respect it.
- `plan.source` (`coursekit.hcl.Source`) reads HCL for things plan JSON omits:
  `plan.source.backend("envs/dev")`, `plan.source.blocks("resource", "google_storage_bucket", under="bootstrap")`.
- `plan.all_changes()` includes deletes. `Resource.previous_address` shows `moved` results, and
  `Resource.replace_paths` shows which attribute forces a replacement.

## Module-scoped lesson tests

Put a lesson test in `tests/<lab|challenge>/modules/<module>/` to run it **inside** that module's
folder (copied as `modules/<module>/tests/lesson_*.tftest.hcl` in the build tree). Use this when a
module declares `configuration_aliases`: a run block in the root can't satisfy aliased providers,
but the module's own folder with `mock_provider "google" { alias = "peer" }` can.

## Contracts: when to fix names

Checks should find resources by type, tag or wiring. Pin a name only when a
**native test** must address it (`google_compute_instance.web` in lesson 03's
test). Say so in `lab.md` ("name it `web`").

## Updating providers

1. Bump the constraint in `shared/terraform/versions.tf` and in every `versions.tf` under `lessons/`.
2. Regenerate the lock file:
   ```powershell
   cd shared/terraform
   terraform init -upgrade -backend=false
   terraform providers lock -platform=windows_amd64 -platform=linux_amd64 -platform=linux_arm64 -platform=darwin_amd64 -platform=darwin_arm64
   ```
3. Run `python course.py selftest`. Provider upgrades can rename attributes the checks read.
