# Troubleshooting 08 — "The backend keeps flapping"

Support tickets: *"The shop shows a 502 error every few minutes, then works again."*
The console's backend view toggles the web VM between **HEALTHY** and
**UNHEALTHY**. NGINX is fine: `curl localhost` on the VM always works.

```powershell
Copy-Item -Recurse lessons/08-load-balancing/broken workspace/08-broken
python course.py check 08 --path workspace/08-broken
```

1. Which requirement fails? Which source does the connectivity model say is blocked?
2. Find the firewall rule for the load balancer. Compare its source ranges with the README.
3. Why would a *partial* range cause **intermittent** failures instead of total failure?
4. Fix it. Where would you record the "magic" ranges so nobody copies an incomplete list again?

Answer: [ANSWER.md](ANSWER.md)
