# Troubleshooting 20 — "The refactor PR wants to delete the reports bucket"

The refactor PR looked perfect in review: the module, a `moved` block for every resource, the
import. Then the plan comment from CI arrived:

```
Plan: 1 to add, 0 to change, 1 to destroy.
```

The author says, "The moved blocks are all there, Terraform must be confused." The reports
bucket holds two years of sales reports.

```powershell
Copy-Item -Recurse lessons/20-advanced-terraform/broken workspace/20-broken
python course.py check 20 --path workspace/20-broken -v
```

1. Which address will be destroyed, and which will be created? Is it the same real bucket?
2. Why didn't `terraform validate` catch the mistake?
3. Fix it. What would have happened if someone had applied this plan?
4. What review habit or CI rule would catch this before a human has to read the plan?

Answer: [ANSWER.md](ANSWER.md)
