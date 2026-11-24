# Troubleshooting 02 — The cycle

A teammate wanted to make sure the web service account "only exists once its
roles are granted", so they added a `depends_on`. Now nothing works.

```powershell
Copy-Item -Recurse lessons/02-gcp-foundations/broken workspace/02-broken
python course.py check 02 --path workspace/02-broken
```

1. Read the error. Which two resources does Terraform name?
2. Draw the dependency edges between them on paper. Where do they come from: references, or `depends_on`?
3. Explain why the teammate's goal is impossible as written. What *should* depend on what?
4. Fix it with the smallest change.

Answer: [ANSWER.md](ANSWER.md)
