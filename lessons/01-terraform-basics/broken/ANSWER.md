# Answer — Troubleshooting 01

**Symptom:** `validate` fails with *Reference to undeclared resource* in `outputs.tf`.

**Root cause:** `bucket_url` refers to `google_storage_bucket.asset`, but the
resource is named `assets`. Resource addresses are `TYPE.NAME`, and the name
is the second label of the resource block, not the bucket's `name` argument.

**Fix:** change `google_storage_bucket.asset.url` to `google_storage_bucket.assets.url`.

**Lesson:** `terraform validate` catches broken references before anything
reaches the cloud. Run it, or `course check`, before every push. Lesson 16 makes
it a pipeline gate.
