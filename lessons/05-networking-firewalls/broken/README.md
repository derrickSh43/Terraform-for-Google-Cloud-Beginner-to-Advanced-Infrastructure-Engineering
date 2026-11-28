# Troubleshooting 05 — "The web server can't reach the app tier"

This folder is a copy of the **lab's reference solution** (tag-based firewall rules),
not your own code. If you finished the challenge, your rules use service accounts
instead, so this folder will look a little different from yours. That's expected.

In this config:

- `compute.tf` holds the **web VM** (`meridian-web-1`, tag `web`).
- `app.tf` holds the **app VM** (`meridian-app-1`, tag `app`). It runs the
  storefront's backend service on port 8080 (`scripts/app-startup.sh`).
- `firewall.tf` holds the rules from the connectivity matrix.

Ticket from the storefront team:

> Since this morning's firewall change, every request from the web VM to the app
> VM on port 8080 times out. The app VM itself is healthy, and IAP SSH to both
> VMs still works. Nothing else changed!

```powershell
Copy-Item -Recurse lessons/05-networking-firewalls/broken workspace/05-broken
python course.py check 05 --path workspace/05-broken
```

1. Which connectivity check fails, and what does the evaluator say decided it?
2. "Implied ingress deny" means none of your rules matched. List every field a rule
   must match (direction, source, target, protocol, port), and check each one in the
   web -> app rule against the two VMs.
3. A **timeout** (not "connection refused") is the classic symptom of a firewall drop. Why?
4. Fix it. Then think: what change from the challenge would have made this mistake impossible?

Answer: [ANSWER.md](ANSWER.md)
