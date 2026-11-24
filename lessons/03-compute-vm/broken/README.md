# Troubleshooting 03 — "But the plan was green!"

`terraform validate` passes and so does `terraform plan`. Yet
`course check` fails, and on a real project `terraform apply` would fail too,
after waiting on the API.

```powershell
Copy-Item -Recurse lessons/03-compute-vm/broken workspace/03-broken
python course.py check 03 --path workspace/03-broken
```

1. Which requirement fails? Read its message carefully.
2. Why can't `validate` or an offline `plan` catch this? What does the provider know without calling Google?
3. Fix it the *right* way, so the same mistake can't recur on the next VM.

Answer: [ANSWER.md](ANSWER.md)
