# Troubleshooting 23 — "The central log bucket is almost empty"

The landing zone went live two weeks ago. Security opens the central bucket to investigate a
suspicious service account in `meridian-shop-prod` and finds... almost nothing: a handful of entries
about folder changes, and no entries at all from any project.

The sink exists, its writer identity has `roles/logging.bucketWriter`, and its filter is empty
(everything).

```powershell
Copy-Item -Recurse lessons/23-enterprise-platform/broken workspace/23-broken
python course.py check 23 --path workspace/23-broken
```

1. Which requirement fails? What exactly is the sink exporting today?
2. Why did nothing error, in the plan or in the logs?
3. Fix it. Are the two missing weeks of project logs recoverable? From where, and for how long?
4. How could a `check` block (lesson 20) or a test catch this class of mistake?

Answer: [ANSWER.md](ANSWER.md)
