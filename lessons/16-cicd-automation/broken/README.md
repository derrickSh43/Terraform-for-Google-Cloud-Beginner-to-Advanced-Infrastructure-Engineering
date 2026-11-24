# Troubleshooting 16 — "A pull request just changed dev"

A contributor opened a draft PR to experiment with a new firewall rule. Minutes
later, dev's firewall had the rule. Nobody had reviewed or merged anything. The
Actions log shows the `apply` job ran for the PR.

```powershell
Copy-Item -Recurse lessons/16-cicd-automation/broken workspace/16-broken
python course.py check 16 --path workspace/16-broken
```

1. Which requirement fails? Which line is missing from the workflow?
2. In real GitHub, would this apply actually have succeeded? Look at how the apply identity is bound (R16.3) and explain what the run would see.
3. Fix the workflow. Then list every control that now stands between a PR and dev.
4. Why should you not rely on the workflow file alone for this protection?

Answer: [ANSWER.md](ANSWER.md)
