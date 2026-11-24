# Troubleshooting 17 — "Nobody was paged"

The storefront was down for 40 minutes on Saturday. Monitoring shows the
"Storefront unreachable" incident **opened two minutes after the outage began**.
It was right there in the console. Yet nobody's phone buzzed.

```powershell
Copy-Item -Recurse lessons/17-observability/broken workspace/17-broken
python course.py check 17 --path workspace/17-broken
```

1. Which requirement fails? Which alert policies are affected?
2. Why does everything still *look* healthy in the console and in `terraform plan`?
3. Fix it. How would you test, before the next outage, that a page actually reaches a phone?
4. What check would you add to CI (lesson 16) so this can't be merged again?

Answer: [ANSWER.md](ANSWER.md)
