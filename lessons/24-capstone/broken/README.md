# Troubleshooting 24 — "The failure analysis says we're fine"

A FinOps review found prod's web tier idle most of the day, and a one-line pull request halved its
minimum size. The plan was small (one autoscaler updated in place), CI was green, and a reviewer
approved it in two minutes. A week later, a zone outage takes out a third of the web VMs during
the evening peak, and the storefront slows to a crawl. The failure analysis everyone pointed to
still says "6 → 4, enough for peak traffic".

```powershell
Copy-Item -Recurse lessons/24-capstone/broken workspace/24-broken
python course.py check 24 --path workspace/24-broken
```

1. Which requirements fail? One is a baseline: which earlier lesson does it come from, and what did
   that lesson promise?
2. What does the zone-loss table say, and what is actually true now? Work out the number yourself.
3. Why didn't anything stop the pull request? Name two places the course's checks would have
   caught it if they had run in CI.
4. Fix it. Either restore the capacity, or keep the cut and change what the business was promised.
   If you choose the second, what else must change besides the table?

Answer: [ANSWER.md](ANSWER.md)
