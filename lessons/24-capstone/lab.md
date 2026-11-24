# Lesson 24 Lab — Prove it, automate it, explain it

```powershell
python course.py start 24
python course.py check 24
```

The starter is the lesson 23 solution, plus `docs/` with an ADR template and two stubs
(`architecture.md`, `failure-analysis.md`). Run the check first. Four requirements already pass
(phases 1–3 and the dev guard rail), and the rest tell you what's missing.

Guard rail: R24.10, dev's plan stays at *No changes*.

---

## Part A — Baselines (R24.1 – R24.4)

1. Read the R24.4 failure. It names an earlier requirement (R21.5) and a resource. Why didn't lesson
   22's checks catch it?
2. Fix it in `modules/postgres`. The replica should be as available as its primary: once promoted,
   it **is** the primary. Use the module's existing `availability_type` input, so dev stays unchanged.
3. Keep R24.1–R24.3 green while you work on the pipeline. Lesson 16's workflow checks are part of
   phase 3, so keep one workflow file, a read-only default token, and static checks without credentials.

## Part B — One pipeline for every root (R24.5)

Rewrite `.github/workflows/terraform.yml`:

1. **Static checks:** validate `envs/dev`, `envs/prod`, `envs/hub`, `envs/platform` and `bootstrap`
   (`init -backend=false`), plus `fmt -check` and the module tests.
2. **PR plans:** one job, `if: github.event_name == 'pull_request'`, with a matrix
   `root: [dev, prod, hub, platform]` and the plan identity.
3. **Applies on main** (`if: github.event_name == 'push' && github.ref == 'refs/heads/main'`), each
   needing the checks and each behind an `environment`:
   - `apply-dev` (environment `dev`);
   - `apply-shared` with a matrix over hub and platform (`environment: ${{ matrix.root }}`);
   - `apply-prod` (environment `prod`), with `needs: [apply-dev, apply-shared]`.
4. The apply jobs use the apply identity, never the plan one.

## Part C — Test the platform modules (R24.6)

For each of `modules/landing-zone`, `modules/project-factory` and `modules/central-logging`, write
`tests/<name>.tftest.hcl` with `mock_provider "google" {}` (the factory also needs `random`), at
least 2 `run` blocks and 3 assertions:

- **landing-zone:** the Meridian folder's parent, the three environment folders, deletion protection,
  the key-creation guardrail, group-only grants.
- **project-factory:** labels, `auto_create_network = false`, `deletion_policy = "PREVENT"`, one budget
  per project, and a run with bad input that uses `expect_failures = [var.projects]`.
- **central-logging:** assert `include_children == true`. That's lesson 23's silent failure, and now
  a test fails if it comes back.

Use `command = plan` and assert on values that come from inputs. Computed IDs are unknown at plan time.

## Part D — Document it (R24.7 – R24.9)

1. **`docs/architecture.md` (R24.7):** a table of the five roots, a paragraph on the request path, and a
   ```` ```mermaid ```` diagram that names every root, both regions (us-central1, us-east1), and every
   component the plans build. The check lists anything missing, by resource type.
2. **`docs/adr/` (R24.8):** at least three records named `NNNN-title.md` (copy `template.md`), each with
   `Status:`, Context (40+ words), Decision, Alternatives considered and Consequences (25+ words each).
   Between them they must cover the landing zone, the network topology and disaster recovery. Write
   about *your* reasons: what you'd tell the reviewer.
3. **`docs/failure-analysis.md` (R24.9):** fill the zone-loss table with one row per prod workload.
   Use the resource address (`module.web.google_compute_region_instance_group_manager.this`; an index like
   `[0]` may be left out). Work out the numbers yourself from `envs/prod/terraform.tfvars` and the
   rules in the README, then let the check confirm them:

   | Workload | Kind | Zones | Minimum capacity | After losing a zone |
   |---|---|---|---|---|
   | `module.web...` | regional MIG | 3 | ? | ? |

## Done?

```powershell
python course.py check 24
python course.py check 24 --challenge
```

Then hand the repository to someone who hasn't seen it and ask them three things: what does prod
look like, why is there a hub, and what happens if us-central1 disappears. Time how long they need.
