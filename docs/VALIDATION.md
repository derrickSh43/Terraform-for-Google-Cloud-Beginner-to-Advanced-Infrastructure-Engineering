# How offline validation works

## Pipeline

`python course.py check NN` (`coursekit/runner.py`):

| # | Stage | Blocking? | Notes |
|---|---|---|---|
| 1 | `terraform fmt -check -recursive` | no (but fails the lab) | Runs on the student's folder |
| 2 | `terraform init` | yes | In a private build dir `.course/build/<id><l|c>/` (e.g. `03l`; short to stay under Windows path limits), using the shared plugin cache and lock file. On Windows, locked providers are junctions to the cache (`terraform.link_providers`): without symlink rights Terraform would copy 115 MB into every root. Never link an unlocked one: Terraform reinstalls it through the link, under every other running check |
| 3 | `terraform validate -json` | yes | Diagnostics are reformatted as `file:line message`. `plan` validates too, so this runs only when the plan failed or the root has import blocks |
| 4 | `tflint` | no | Only when installed |
| 5 | `terraform plan -refresh=false -out` → `terraform show -json` | yes | Fake OAuth token; plan JSON saved to the build dir |
| 6 | `terraform test` | yes, if the lesson ships tests | Lesson tests in `tests/lab/` and `tests/challenge/` are copied into the build dir. They use `mock_provider`. |
| 7 | Requirement checks | yes | `lessons/NN-*/checks.py` functions run against the plan. A requirement with `test=` also needs that lesson test to pass |

The student's folder is never modified. Files are mirrored into the build dir,
along with:

- `zz_course_backend_override.tf`, which forces `backend "local"`. Any
  `backend "gcs"` the student writes (lesson 6+) still plans offline.
- `.terraform.lock.hcl` from `shared/terraform/`, if the student has none.

## Multi-root lessons and prepared state

Lessons can declare several roots (`envs/dev`, `envs/prod`, `bootstrap`). Stages
2–5 run for each root (`plan (dev)`, `plan (prod)`, ...), up to three at a time. When a lesson ships a
state file for a root, the plan is computed against it (`-refresh=false`, no API
calls), which turns "would this refactor destroy production?" into an offline
question. See [AUTHORING.md](AUTHORING.md#multi-root-lessons-and-deployed-state-lesson-06-onward).

### Import blocks (lesson 20+)

A real `import` reads the object from the Google API. Instead, a lesson can ship an inventory of
objects that exist in the cloud but not in state (`"cloud": {"dev": "state/dev.cloud.json"}`, built
with `coursekit.cloudsim.build_inventory` from a fabricated state). Before each plan, `cloudsim`
resolves the root's import blocks against it and writes found objects into the prepared state at the
`to` address. Terraform skips imports whose target is already in state, so the plan then shows exactly
what a real post-import plan shows. IDs that aren't in the inventory fail the plan. Checks read
`plan.imported` (address -> id).

A shipped state may contain deliberate drift (`"expected_drift"` in lesson.json): the freshness
self-test then accepts in-place updates on those addresses only.

## Why a plan works without Google credentials

The Google provider doesn't call any API when planning **new** resources with
`-refresh=false`. With `GOOGLE_OAUTH_ACCESS_TOKEN` set to a dummy value, provider
configuration succeeds and the plan is computed locally. This was verified with
`hashicorp/google` 8.12.

What does **not** work offline:

| Construct | Why | Course approach |
|---|---|---|
| Data sources that read GCP (`google_compute_zones`, `google_project`, ...) | Real API call → 401 | Labs avoid them; use variables. `google_client_config` is fine. |
| `import` blocks | Must read the real resource | Lesson 20 uses prepared state files |
| Refresh / drift detection | Reads real resources | Simulated with edited state files |
| Server-side validation (invalid zone, quota) | Only the API knows | Requirement checks catch common cases. See broken repo 03. |

## Writing robust checks

Checks receive a `coursekit.plan.Plan`:

```python
plan.resources("google_compute_instance")      # by type, any name
plan.by_tag("web")                             # VMs with a network tag
vm.get("boot_disk.0.initialize_params.0.image")
vm.is_unknown("network_interface.0.access_config.0.nat_ip")
vm.references_type("google_service_account", "service_account")
plan.linked(vm, "google_compute_subnetwork", "network_interface.subnetwork")
plan.variable_value("region"); plan.outputs(); plan.output_references("x")
plan.provider_constraint("google"); plan.provider_references("google", "project")
```

Rules of thumb:

1. **Find resources by type or tag, not by address**, unless the lab states a naming contract.
2. **Check values, then wiring.** "The VM's subnet is private" is better than "the subnet is called web".
3. **Handle unknowns.** Values computed at apply time show up in `after_unknown`. Fall back to `references(...)`.
4. **Write messages for a beginner.** Say what was found and what was expected. Put the fix in `hint=`.
5. **Every requirement needs a fixture that breaks it.** If `selftest` can't make a requirement fail, it's checking nothing.

## The firewall evaluator

`coursekit/firewall.py` models VPC firewall rule evaluation (priority, deny-wins
ties, implied rules, tag and service-account targets, egress then ingress, and
external IP reachability). It answers connectivity questions without a live
network and reports which rule decided. Unit tests are in `tests/test_firewall.py`.

It also models internet **egress** (since lesson 07): a VM without an external IP
needs a Cloud NAT in its region and network that covers its subnet, and the
Google API VIPs are reachable through Private Google Access. Peered or on-prem
sources are modelled with `fw.internal_ip("10.110.0.10")`.

Known simplifications: no hierarchical/network firewall policies, no custom
routes (peering is verified by checks, not routed), and VM IPs are approximated
by their subnet's range.

## Workflows and student tests (lesson 16+)

`coursekit/workflow.py` reads `.github/workflows/*.yml` with a small YAML-subset parser
(no PyYAML needed). Checks inspect triggers, `permissions:`, job conditions, `needs`,
environments and `google-github-actions/auth` steps. Any `modules/<name>/tests/*.tftest.hcl`
files students write run as a separate `tests (modules/<name>)` stage.

## Failure-domain analysis (lesson 21+)

`coursekit/failure.py` turns a plan into workloads with failure domains: a regional MIG spreads over
`distribution_policy_zones` (or the region's zones) with capacity from its autoscaler; VMs, zonal MIGs,
ZONAL Cloud SQL and zonal GKE clusters live in one zone; REGIONAL Cloud SQL, regional GKE and
STANDARD_HA Memorystore fail over. `worst_case(plan)` removes each zone in turn and reports the lowest
capacity left (EVEN distribution: a zone holds at most `ceil(n / zones)` instances). A ZONAL database
without a location preference counts as "one zone, chosen by Google".

### Region loss (lesson 22+)

`failure.data_stores(plan)` lists buckets, Cloud SQL primaries (with their replicas) and Artifact Registry
repositories with the regions holding a copy and the RPO their architecture can achieve: regional bucket =
data lost; dual/multi-region = 720 min (15 with `ASYNC_TURBO`); SQL with a cross-region replica = 1 min,
backups only = 1440 min; multi-region registry = 0. `lose_region(plan, region)` says which survive.

## Baselines and checked documentation (lesson 24)

`coursekit.baseline.require_all(plan, ids)` re-runs earlier lessons' requirements (by ID, e.g. `R21.5`)
against the current plans, so a later change that breaks an earlier guarantee fails loudly.
`coursekit.docs` reads the markdown students write: decision records are measured against the lesson's
`rubric.json` (status line, required sections with minimum word counts, topics covered), the mermaid
diagram must mention each component type present in the plans, and numbers in failure-analysis tables
are compared with `coursekit.failure`. Prose quality is not judged; structure and facts are.

## Load balancer tracing

`coursekit/lb.py` follows a global external Application Load Balancer from its
forwarding rule to the VMs: `lb.trace(plan)` returns one `Frontend` per
forwarding rule, with the proxy, URL map, HTTPS redirect flag and backends
(instance groups, resolved VMs, named port, health checks), plus a list of
human-readable problems for every broken link. Checks combine it with the
firewall evaluator, using Google's front-end ranges as sources.

## Self-test

`python course.py selftest` proves the validators correct, for every `ready` lesson:

- `starter/` passes fmt, init and validate, and contains the previous lesson's solution unchanged;
- `solution/` passes all lab requirements; `solution-challenge/` passes lab + challenge;
- every `fixtures/<name>/` (files overlaid on a solution) fails on the IDs/stage in its `expect.json`;
- `broken/` fails as its `expect.json` states.
