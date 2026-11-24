# Answer — Troubleshooting 20

**Fault:** a typo in `envs/dev/refactor.tf`:

```hcl
moved {
  from = google_storage_bucket.reports
  to   = module.reporting.google_storage_bucket.report   # should be .reports
}
```

1. Terraform followed the `moved` block and moved the deployed bucket to
   `module.reporting.google_storage_bucket.report`. No resource block has that address, so that
   object is planned for **destroy**. Meanwhile `module.reporting.google_storage_bucket.reports`
   has configuration but no object, so it's planned for **create**. Both have the same bucket name:
   the destroy deletes the real bucket and its data, and the create then makes an empty one.
   R20.2 ("not moved from google_storage_bucket.reports") and R20.3 (DESTROYED) both fail.
2. A `moved` block whose `to` has no configuration is **valid**: it's how you move something to an
   address you then remove. Unlike an `import` block, Terraform can't tell a typo from intent.
3. Fix the address to `module.reporting.google_storage_bucket.reports`. Applying the broken plan
   would have deleted the bucket. With `force_destroy = false` (the default), the destroy fails on a
   bucket that still has objects, which is the only reason this would be survivable. Never rely on that.
4. Fail CI on any destroy in a refactor PR (lesson 16's plan job can parse `terraform show -json`
   and reject `delete` actions unless the PR has an explicit label). Add `prevent_destroy` on data
   buckets (the challenge), and compare `terraform state list` before and after the refactor.
