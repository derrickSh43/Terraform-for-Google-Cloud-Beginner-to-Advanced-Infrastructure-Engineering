# Answer — Troubleshooting 03

**Symptom:** R3.2 fails: `zone 'us-central1' is not a zone inside region 'us-central1'`.

**Root cause:** `zone = "us-central1"` is a *region*. VMs are zonal. The
argument is just a string to Terraform, so `validate` accepts it. The provider
only learns it's invalid when the Compute API rejects it at **apply** time.

**Fix:** use `zone = var.zone` (default `"us-central1-a"`). For prevention, add a
validation to the variable:

```hcl
validation {
  condition     = can(regex("^[a-z]+-[a-z]+[0-9]-[a-z]$", var.zone))
  error_message = "zone must look like us-central1-a."
}
```

**Lesson:** a successful plan proves the configuration is *coherent*, not that
the cloud will *accept* it. Policy checks like this course's validators, and in
lesson 16 CI policy gates, catch a class of errors that would otherwise only
appear at apply.
