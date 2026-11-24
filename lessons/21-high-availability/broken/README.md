# Troubleshooting 21 — "The API went dark right after the HA rollout"

The HA change applied cleanly in dev. Ten minutes later:

- the storefront loads, but every API call times out;
- the internal load balancer's console page says **0 of 2 backends healthy**;
- the app MIG keeps recreating VMs: `instance is unhealthy, recreating` every few minutes.

SSH through IAP to an app VM works, and `curl localhost:8080/health.json` returns `{"status": "ok"}`.

```powershell
Copy-Item -Recurse lessons/21-high-availability/broken workspace/21-broken
python course.py check 21 --path workspace/21-broken
```

1. Which requirement fails? Why does `curl` on the VM succeed when the health check fails?
2. Why are *both* symptoms (no traffic, VMs recreated) caused by the same mistake?
3. Fix it. How would you have noticed in the plan, before applying?
4. The web tier has the same kind of rule and works. Where did the mistake probably come from?

Answer: [ANSWER.md](ANSWER.md)
