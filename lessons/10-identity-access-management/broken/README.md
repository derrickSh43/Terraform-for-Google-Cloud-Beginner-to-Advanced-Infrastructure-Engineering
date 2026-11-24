# Troubleshooting 10 — "Simpler than per-account grants"

The cleanup PR looks great: no keys, no Editor, no binding. But the weekly
security scan now flags a new **HIGH** finding:

> *Principal `group:meridian-platform@meridianbooks.example` can impersonate 4
> service accounts in project `meridian-dev-4821`.*

The PR author: *"That's intended, the platform team needs to impersonate CI."*

```powershell
Copy-Item -Recurse lessons/10-identity-access-management/broken workspace/10-broken
python course.py check 10 --path workspace/10-broken
```

1. Which requirement fails? Where is the impersonation grant attached?
2. List every service account the group can now act as. Which one is the most dangerous, and why?
3. Fix it so the group can impersonate **only** `meridian-ci`.
4. Which other IAM role has the same "everywhere at project level" trap? (Look at `IMPERSONATION_ROLES` in `checks.py`.)

Answer: [ANSWER.md](ANSWER.md)
