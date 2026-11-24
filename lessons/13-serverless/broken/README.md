# Troubleshooting 13 — "We just needed a URL to test against"

The frontend team couldn't call the catalog API from their laptops, so a change
went in. Two days later the catalog's request logs show traffic from scrapers,
none of it through the load balancer, and Cloud Armor rules added in front of the
load balancer seem to have no effect on it.

```powershell
Copy-Item -Recurse lessons/13-serverless/broken workspace/13-broken
python course.py check 13 --path workspace/13-broken
```

1. Which requirement fails? Which **two** settings together made the service public?
2. Why do protections on the load balancer (Cloud Armor, TLS policy, logging) not apply to this traffic?
3. Fix it. How can the frontend team test without a public endpoint?
4. If you could keep only one of the two fixes, which matters more, and why?

Answer: [ANSWER.md](ANSWER.md)
