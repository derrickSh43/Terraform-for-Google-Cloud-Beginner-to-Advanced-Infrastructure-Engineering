# Lesson 21 Challenge — Objectives, budgets and peak

```powershell
python course.py check 21 --challenge
```

| ID | Requirement |
|---|---|
| C21.1 | **Availability SLO.** A `modules/slo` with `google_monitoring_custom_service` and `google_monitoring_slo`: `goal = 0.995`, `rolling_period_days = 28`, and a `request_based_sli.good_total_ratio` that counts `loadbalancing.googleapis.com/https/request_count` for this environment's forwarding rule (`<name_prefix>-http`): total requests, and bad = `response_code_class="500"`. |
| C21.2 | **Fast-burn alert.** A `google_monitoring_alert_policy` whose condition filter is `select_slo_burn_rate("<slo id>", "3600s")`, threshold about 13.44 (2% of the budget in an hour), notifying the on-call channel from `module.observability`. |
| C21.3 | **Peak survives a zone loss.** Peak traffic needs 6 web VMs. Set prod's `web_max_replicas` so that 6 remain after losing any zone. |
| C21.4 | **MIG guard rails.** In `mig-service`, reject fewer than two zones, and reject `min_replicas` below the number of zones (a zone would run nothing). The lesson test runs inside `modules/mig-service` (`tests/challenge/modules/mig-service`). |

## Contract for the lesson test

The test runs inside `modules/mig-service` with lesson 09's inputs, so any variable you add needs a default.
It looks for `google_compute_region_instance_group_manager.this`.

## Think about it

- Why measure the SLI at the load balancer and not with the uptime check from lesson 17? What does each one miss?
- A slow-burn alert (say a 6-hour window, rate 6) catches what the fast-burn alert doesn't. Give an example.
- After C21.4, could someone still deploy a tier that doesn't survive a zone loss with this module? How?
