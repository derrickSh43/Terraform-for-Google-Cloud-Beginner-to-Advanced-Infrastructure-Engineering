# Lesson 09 Challenge — Scaling like you mean it

```powershell
python course.py check 09 --challenge
```

| ID | Requirement |
|---|---|
| C9.1 | After a spike, the autoscaler may drop several VMs at once, then need them again a minute later. Add `scale_in_control`: at most **1** VM removed per **10 minutes**. |
| C9.2 | Meridian's traffic doubles on weekday business hours. Pre-scale **prod only** with a `scaling_schedules` entry (min 4 VMs, `0 8 * * MON-FRI`, `America/Chicago`, 10 h). Drive it from a module variable `business_hours_min_replicas` (0 = no schedule) and a `dynamic` block. |
| C9.3 | CPU isn't the only bottleneck. Add `load_balancing_utilization { target = 0.8 }`, which pairs with the backend's `max_utilization`. |
| C9.4 | `max_replicas` must be at least `min_replicas`, and at most 20. Write a validation that references **both** variables (allowed since Terraform 1.9). `tests/challenge/mig_module.tftest.hcl` checks it against the module directly. |

## Contract for the lesson test

The test calls the module on its own with the lab's nine required inputs, so every other variable needs a default. It looks for
`google_compute_region_instance_group_manager.this` and `google_compute_region_autoscaler.this`.

## Think about it

- With several signals (CPU, load balancer, schedule), the autoscaler picks the **largest** recommendation. Why is that the safe choice?
- Scale-out is fast and scale-in is slow on purpose. What does each protect against?
