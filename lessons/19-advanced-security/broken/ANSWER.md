# Answer — Troubleshooting 19

**Symptom:** R19.2: `The Cloud Storage service agent can't use the key - every write to a CMEK bucket would fail`.

**Root cause:** with a default KMS key on a bucket, **Cloud Storage** encrypts objects as its
service agent, `service-<project number>@gs-project-accounts.iam.gserviceaccount.com`. The broken
`kms` module never grants that agent `roles/cloudkms.cryptoKeyEncrypterDecrypter`. Every new object
write, from the app's backup job or the audit log sink, fails with 403.

**Why granting meridian-app doesn't help:** the app never touches the key. It hands bytes to Cloud
Storage, and Cloud Storage calls KMS with its own identity.

**Fix:** restore

```hcl
resource "google_kms_crypto_key_iam_member" "storage_agent" {
  crypto_key_id = google_kms_crypto_key.storage.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:service-${var.project_number}@gs-project-accounts.iam.gserviceaccount.com"
}
```

and keep `depends_on = [google_kms_crypto_key_iam_member.storage_agent]` on the `storage_key_id`
output. On a fresh environment, Terraform would otherwise set the bucket's default key in parallel
with (or before) the grant. The bucket update itself fails, or the first writes do.

**Why old objects still work:** a bucket's default key applies to **new** objects. Objects
written before the change keep their original (Google-managed) encryption. Reads succeed, so
monitoring looking only at reads stays green. Lesson 17's alerting on the sink and on backup
job errors would have caught it.
