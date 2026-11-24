# Troubleshooting 06 — The refactor PR

A teammate opened the "move dev into modules" PR. CI posted this plan for dev:

```
Plan: 1 to add, 1 to change, 1 to destroy.
```

Their comment: *"Just one subnet recreated, and the VM gets an in-place update.
Low risk, approving myself."*

```powershell
Copy-Item -Recurse lessons/06-terraform-state-modules/broken workspace/06-broken
python course.py check 06 --path workspace/06-broken
```

1. Which resource would be destroyed? Which would be created, and which updated?
2. Why does the **app VM** change at all, when nobody touched `vm-service`?
3. In the real world, what happens to the API while this applies? (Can a subnet be deleted while a VM uses it?)
4. Fix it with one block. Then explain why "only 1 to destroy" was never low risk.

Answer: [ANSWER.md](ANSWER.md)
