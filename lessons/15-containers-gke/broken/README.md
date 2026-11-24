# Troubleshooting 15 — "We just wanted kubectl from home"

Connecting through the ops VPC was "too slow" for the data team, so someone
changed the cluster module: *"public endpoint + allow all, the API needs auth
anyway."* A week later the cluster's audit logs show thousands of anonymous
requests to `/version`, `/api` and `/apis` from all over the world.

```powershell
Copy-Item -Recurse lessons/15-containers-gke/broken workspace/15-broken
python course.py check 15 --path workspace/15-broken
```

1. Which requirement fails? What exactly is exposed?
2. "The API needs authentication anyway." Why is that not enough? (Think: zero-days, misconfigured RBAC, anonymous endpoints, credential stuffing.)
3. Revert it. What is the supported way for the data team to reach the cluster?
4. Could Terraform simply flip `enable_private_endpoint` back on the deployed cluster? Look at the plan.

Answer: [ANSWER.md](ANSWER.md)
