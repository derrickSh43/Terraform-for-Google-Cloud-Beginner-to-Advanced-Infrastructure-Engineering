# Answer — Troubleshooting 23

**Fault:** `include_children` is missing from `google_logging_folder_sink.central`, and it defaults to `false`.

1. R23.6 fails: "include_children = true - otherwise only the folder's own logs are exported". The
   sink exports only logs about the **folder resource itself** (folder IAM and policy changes), not
   logs from the projects under it.
2. A sink without children is perfectly valid: some teams want exactly that. Terraform and Cloud
   Logging can't know what you meant, and nothing failed, so nothing was logged about it.
3. Add `include_children = true`. The missing entries are still in each project's `_Default` log
   bucket, which keeps them **30 days** by default (`_Required` audit logs: 400 days). Query them
   there (or copy them with a log-bucket *copy* job) before they age out. Audit logs in `_Required`
   are safe for longer.
4. A `check` block in `central-logging` can assert
   `google_logging_folder_sink.central.include_children`, and a module test can assert it with a mock
   provider. Better still, make the sink's settings non-optional in the module, so callers can't get it wrong.
