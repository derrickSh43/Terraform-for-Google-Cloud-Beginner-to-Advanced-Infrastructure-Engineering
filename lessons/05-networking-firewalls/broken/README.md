# Troubleshooting 05 — "The API is down"

Ticket from the storefront team:

> Since this morning's change, every request from the web server to the API
> (port 8080) times out. The API VM is healthy. IAP SSH to both VMs still works.
> Nothing else changed!

```powershell
Copy-Item -Recurse lessons/05-networking-firewalls/broken workspace/05-broken
python course.py check 05 --path workspace/05-broken
```

1. Which connectivity check fails, and what does the evaluator say decided it?
2. "Implied ingress deny" means none of your rules matched. List every field a rule must match, and check each one against the web -> app rule.
3. A **timeout** (not "connection refused") is the classic symptom of a firewall drop. Why?
4. Fix it. Then think: what change from the challenge would have made this typo impossible?

Answer: [ANSWER.md](ANSWER.md)
