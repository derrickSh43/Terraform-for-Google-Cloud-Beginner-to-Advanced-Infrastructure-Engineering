# Lesson 03 Challenge — Cheaper, safer, configurable

```powershell
python course.py check 03 --challenge
```

| ID | Requirement |
|---|---|
| C3.1 | Make the machine type a variable `machine_type` (default `e2-micro`) that **rejects** anything except `e2-micro`, `e2-small` and `e2-medium`. `tests/challenge/machine_type.tftest.hcl` must pass. It plans with `n2-standard-8` **on purpose** and expects your validation to reject it (see *Why does the test send a bad value on purpose?* in lesson 02's challenge). The test looks for your VM at `google_compute_instance.web`. |
| C3.2 | Replace `startup.sh` with a template `scripts/startup.sh.tftpl` rendered by `templatefile()`. The home page must show the environment name (`dev`). |
| C3.3 | Block project-wide SSH keys on this VM. |
| C3.4 | Dev VMs should be **Spot** VMs (much cheaper, can be reclaimed). Production must stay `STANDARD`. Use a conditional expression on `var.environment`. |

Tip for C3.4: look at the `scheduling` block. Spot VMs need
`provisioning_model = "SPOT"`, `preemptible = true` and `automatic_restart = false`.
Then try `environment = "prod"` in `terraform.tfvars` and re-run the check.
