# Troubleshooting 01 — "It worked on my machine"

A teammate pushed this configuration on Friday. On Monday the pipeline fails at
`terraform validate`. Fix it **without rewriting the configuration**. Find the
smallest change.

```powershell
python course.py check 01 --path lessons/01-terraform-basics/broken
```

Steps:

1. Read the error. Note the file, the line, and what Terraform says is wrong.
2. Explain the root cause in one sentence before you change anything.
3. Fix it in a copy. Don't edit this folder, so the exercise stays reusable:
   ```powershell
   Copy-Item -Recurse lessons/01-terraform-basics/broken workspace/01-broken
   python course.py check 01 --path workspace/01-broken
   ```

Stuck after 15 minutes? Read [ANSWER.md](ANSWER.md).
