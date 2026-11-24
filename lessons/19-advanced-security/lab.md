# Lesson 19 Lab — Layered security on a live platform

```powershell
python course.py start 19
python course.py check 19
```

The starter is the lesson 18 solution plus three empty modules (`kms`, `cloud-armor`,
`org-policies`) and `state/dev.tfstate` (dev after lesson 18). R19.8 and R19.9 are guard rails.

---

## Part A — Keys (R19.1 – R19.3)

1. `modules/kms` (inputs: `environment`, `region`, `project_number`, `rotation_days` = 90, `labels`):
   - `google_project_service` for `cloudkms.googleapis.com`
   - `google_kms_key_ring` `meridian-<env>` in `var.region`
   - `google_kms_crypto_key` `storage`: `purpose = "ENCRYPT_DECRYPT"`, `rotation_period = "${var.rotation_days * 86400}s"`,
     `lifecycle { prevent_destroy = true }`
   - `google_kms_crypto_key_iam_member`: `roles/cloudkms.cryptoKeyEncrypterDecrypter` for
     `serviceAccount:service-${var.project_number}@gs-project-accounts.iam.gserviceaccount.com`
   - output `storage_key_id` with `depends_on = [google_kms_crypto_key_iam_member.storage_agent]`
2. `modules/foundation` and `modules/observability`: a `kms_key_id` variable (default `null`) and, on
   the backups and audit buckets:

   ```hcl
   dynamic "encryption" {
     for_each = var.kms_key_id == null ? [] : [var.kms_key_id]
     content { default_kms_key_name = encryption.value }
   }
   ```
3. In both environments, call `module "kms"` and pass `kms_key_id = module.kms.storage_key_id` to
   `foundation` and `observability`.

## Part B — Cloud Armor (R19.4 – R19.6)

`modules/cloud-armor` (inputs `name`, `requests_per_minute`): one `google_compute_security_policy` with:

| priority | rule |
|---|---|
| 1000 | `deny(403)` on `evaluatePreconfiguredWaf('sqli-v33-stable', {'sensitivity': 1})` |
| 1100 | `deny(403)` on `evaluatePreconfiguredWaf('xss-v33-stable', {'sensitivity': 1})` |
| 2000 | `throttle` for `src_ip_ranges = ["*"]`, `rate_limit_options { conform_action = "allow"  exceed_action = "deny(429)"  enforce_on_key = "IP"  rate_limit_threshold { count = var.requests_per_minute  interval_sec = 60 } }` |
| 2147483647 | `allow` (default) |

In `modules/http-lb`, add a `security_policy` variable and set it on **both** backend services.
Environments: dev 600, prod 1200 requests per minute.

## Part C — Guardrails (R19.7, R19.8)

`modules/org-policies`: enable `orgpolicy.googleapis.com`, then a `google_org_policy_policy`
(`name = "projects/<id>/policies/<constraint>"`, `parent = "projects/<id>"`) with
`spec { rules { enforce = "TRUE" } }` for each boolean constraint (`storage.uniformBucketLevelAccess`,
`storage.publicAccessPrevention`, `sql.restrictPublicIp`, `iam.disableServiceAccountKeyCreation`),
plus `compute.vmExternalIpAccess` with `rules { deny_all = "TRUE" }`.

Before you add each one, look at R19.8. Would anything deployed already violate it?

## Review

Dev: **11 to add, 4 to change, 0 to destroy**. Then try the trap: add
`encryption_key_name = var.kms_key_id` to the Cloud SQL instance and re-run the check. What does R19.9 say,
and why? Revert it.

## Reflection questions

1. You disable the storage key. What happens to the backups bucket? Who can still read the objects?
2. Why grant `cryptoKeyEncrypterDecrypter` to the Cloud Storage service agent and not to `meridian-app`, which writes the backups?
3. A rule in `preview` matched 10,000 SQL-injection requests yesterday. What reached the backends?
4. Org policies block the API for everyone. How would you handle a legitimate exception (e.g. one VM that must have an external IP)?
