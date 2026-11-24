# Troubleshooting 09 — "The MIG eats its own VMs"

After someone "tuned autohealing to be faster", the web MIG never stabilises.
The console shows VMs going `CREATING → RUNNING → DELETING` over and over. The
load balancer reports 0 healthy backends, and the shop is down. NGINX logs on the
VMs are always cut off mid-install.

```powershell
Copy-Item -Recurse lessons/09-autoscaling-mig/broken workspace/09-broken
python course.py check 09 --path workspace/09-broken
```

1. Which requirement fails? What value is the MIG actually using?
2. Add up roughly how long a new VM needs before NGINX answers: boot, `apt-get update`, `apt-get install nginx`, start.
3. Explain the loop in your own words. Why does it never end on its own?
4. Fix it. Which of the two health checks (load balancer vs autohealing) should react faster, and why?

Answer: [ANSWER.md](ANSWER.md)
