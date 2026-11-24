# Lesson 17 Challenge — SLOs and dashboards

```powershell
python course.py check 17 --challenge
```

| ID | Requirement |
|---|---|
| C17.1 | **An availability SLO.** `google_monitoring_custom_service` + `google_monitoring_slo` with a request-based SLI (good = non-5xx load balancer requests, total = all), `goal = 0.995` over a rolling 28 days. Then an alert on `select_slo_burn_rate("<slo id>", "3600s") > 10`: the error budget is burning 10× faster than allowed. |
| C17.2 | **A dashboard** (`google_monitoring_dashboard`, `jsonencode(...)`) with storefront requests by response class and Cloud SQL CPU. |
| C17.3 | **Database pressure.** Alert when `cloudsql.googleapis.com/database/cpu/utilization` stays above 80% for 10 minutes, for this instance. Add an `instance_name` output to the postgres module. |
| C17.4 | **No typo'd pager.** Validate `oncall_email`. `tests/challenge/observability_module.tftest.hcl` tries addresses without `@` and without a domain. |

## Think about it

- 99.5% over 28 days allows how many minutes of downtime? What does a burn rate of 10 mean in hours until the budget is gone?
- Why page on burn rate instead of on every individual 5xx spike?
