# Troubleshooting 07 — "NAT is there, apt still hangs"

A teammate merged a cost optimisation: *"NAT only for the subnet that serves
customers."* Monitoring shows the Cloud NAT gateway exists and is healthy, yet
the app VM's startup script still times out on `apt-get update`.

```powershell
Copy-Item -Recurse lessons/07-cloud-networking-ii/broken workspace/07-broken
python course.py check 07 --path workspace/07-broken
```

1. Which requirement fails, and what does the connectivity model say about the app VM?
2. Open `modules/network/main.tf`. Which subnet does the NAT serve, and which VMs live there?
3. Does the web VM even use NAT? (Hint: R7.4.) So what did the "optimisation" actually save?
4. Fix it, and add a guard so this mistake can't reach review again.

Answer: [ANSWER.md](ANSWER.md)
