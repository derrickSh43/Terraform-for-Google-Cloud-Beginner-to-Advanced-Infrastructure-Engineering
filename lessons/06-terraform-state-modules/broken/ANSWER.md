# Answer — Troubleshooting 06

**Symptom:** R6.8: `google_compute_subnetwork.app would be DESTROYED` and
`module.network.google_compute_subnetwork.this["app"] would be CREATED`.

**Root cause:** `envs/dev/moved.tf` has no `moved` block for the app subnet. The
deployed subnet is still recorded at its lesson 05 address
`google_compute_subnetwork.app`. The new code declares
`module.network.google_compute_subnetwork.this["app"]`, which isn't in state.
So Terraform plans to delete the old one and create a new one.

**Why the VM changes:** the app VM's `subnetwork` comes from the new subnet's ID,
which is *unknown until the new subnet exists*. So the VM must be updated to point
at it. That cascade is the real damage: the VM is moved between subnets and its
internal IP changes. In practice, the delete would also fail or stall, because
GCP won't delete a subnet that still has VMs in it. You'd be left with a
half-applied change mid-outage.

**Fix:**

```hcl
moved {
  from = google_compute_subnetwork.app
  to   = module.network.google_compute_subnetwork.this["app"]
}
```

The plan returns to `0 to add, 0 to change, 0 to destroy`.

**Lesson:** for a refactor, the only acceptable plan is **no changes**. Any
destroy in a "pure refactor" PR is a bug, and a small number can hide a large
blast radius. Read *which* resources and *why* (`# forces replacement`,
`known after apply`), not just the totals.
