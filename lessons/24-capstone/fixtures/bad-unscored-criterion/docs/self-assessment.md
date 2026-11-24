# Self-assessment

Scores use the rubric in the lesson (`1` missing, `2` partial, `3` solid, `4` exemplary).
Evidence points at files in this repository.

| Criterion | Score (1-4) | Evidence |
|---|---|---|
| Design | 3 | docs/architecture.md, docs/adr/0001-landing-zone.md |
| Build | 3 | envs/prod/main.tf, modules/project-factory/main.tf |
| Secure | 3 | modules/kms/main.tf, modules/cloud-armor/main.tf, modules/landing-zone/main.tf |
| Automate | 4 | .github/workflows/terraform.yml |
| Monitor | 3 | modules/observability/main.tf, modules/central-logging/main.tf |
| Scale | 3 | modules/mig-service/main.tf, docs/failure-analysis.md |
| Document | 3 | docs/adr/0002-hub-and-spoke.md, docs/adr/0003-cross-region-dr.md |

## What I'd do next

- Load-test the failover runbook: promote the replica in a sandbox and time it against the RTO.
- Alert on replication lag so the database RPO is measured, not assumed.
