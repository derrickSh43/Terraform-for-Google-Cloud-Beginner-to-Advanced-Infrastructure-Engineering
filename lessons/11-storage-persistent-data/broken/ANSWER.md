# Answer — Troubleshooting 11

**Symptom:** R11.2: `The instance must ignore_changes = [attached_disk]`.

**Root cause:** the attachment is managed by `google_compute_attached_disk`,
but `google_compute_instance.this` also owns the `attached_disk` argument, which it
declares as *empty*. After the first apply the instance's real state includes the
data disk. On the next plan, Terraform compares the instance config (no attached
disks) with reality (one disk) and plans to remove it. Then the attachment resource
plans to add it back. The two resources fight forever.

**Why the first plan looked fine:** before the first apply the disk wasn't
attached yet, so there was nothing to remove. Perpetual diffs typically appear
**one apply later**, which is why they slip through review.

**Fix:**

```hcl
resource "google_compute_instance" "this" {
  # ...
  lifecycle {
    ignore_changes = [attached_disk]
  }
}
```

It tells Terraform: "this argument is managed elsewhere; never plan changes to it."

**Same pattern elsewhere:** any setting with both an inline form and a separate
resource, e.g. `google_compute_instance_group.instances` vs
`google_compute_instance_group_membership`, or a bucket's IAM via
`google_storage_bucket_iam_policy` vs `_member`. Pick one owner per setting.
If you must use both, `ignore_changes` on the other.
