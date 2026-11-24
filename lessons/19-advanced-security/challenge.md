# Lesson 19 Challenge — Supply chain, DDoS and exfiltration

```powershell
python course.py check 19 --challenge
```

| ID | Requirement |
|---|---|
| C19.1 | **Binary Authorization policy.** `default_admission_rule` `ALWAYS_DENY` with `ENFORCED_BLOCK_AND_AUDIT_LOG`, `admission_whitelist_patterns` for `${module.registry.repository_url}/*`, and `global_policy_evaluation_mode = "ENABLE"` for Google's system images. The GKE cluster from lesson 15's challenge enforces it. |
| C19.2 | **Adaptive Protection.** Turn on `layer_7_ddos_defense_config` in the Cloud Armor policy. |
| C19.3 | **VPC Service Controls, dry run.** A `google_access_context_manager_service_perimeter` around the project restricting `storage`, `sqladmin`, `secretmanager` (and `bigquery`), with `use_explicit_dry_run_spec = true`. The access policy ID is an organization-level variable. |
| C19.4 | **Rotation guard rail.** `rotation_days` must be 1–90. The lesson test runs inside `modules/kms` (`tests/challenge/modules/kms`). |

## Think about it

- Why start a VPC-SC perimeter in dry-run mode? What breaks most often when it's enforced?
- With `ALWAYS_DENY` as the default, how does a new team get their images allowed, and who should approve that change?
