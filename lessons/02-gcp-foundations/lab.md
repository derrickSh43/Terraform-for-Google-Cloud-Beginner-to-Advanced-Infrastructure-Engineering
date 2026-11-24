# Lesson 02 Lab — APIs and an identity for the web tier

```powershell
python course.py start 02
python course.py check 02
```

Your starter is the lesson 01 solution plus two empty files: `apis.tf` and `iam.tf`.

---

## Step 1 — Enable the APIs (R2.1, R2.2)

Meridian needs these APIs:

```
compute.googleapis.com     iam.googleapis.com      storage.googleapis.com
logging.googleapis.com     monitoring.googleapis.com
```

You could write five resource blocks. Instead, here is a preview of `for_each`,
which lesson 6 covers properly:

```hcl
locals {
  required_apis = toset([
    "compute.googleapis.com",
    # ... the rest
  ])
}

resource "google_project_service" "apis" {
  for_each = local.required_apis

  service            = each.value
  disable_on_destroy = false
}
```

Run `python course.py check 02` and look at the plan line. How many
`google_project_service` instances are planned? Their addresses look like
`google_project_service.apis["iam.googleapis.com"]`.

## Step 2 — A service account (R2.3, R2.7)

In `iam.tf`, create a `google_service_account`:

- `account_id`: 6–30 characters, lowercase, e.g. `meridian-web`
- `display_name` and `description`
- `depends_on = [google_project_service.apis]`. Nothing in the account's arguments
  references the API resource, so Terraform can't infer this ordering. This is a
  legitimate use of `depends_on`.

## Step 3 — Grant only what's needed (R2.4 – R2.6)

The web VMs must write logs and metrics, and nothing else. Grant
`roles/logging.logWriter` and `roles/monitoring.metricWriter` using
**`google_project_iam_member`**:

```hcl
member = "serviceAccount:${google_service_account.web.email}"
```

Do not use `google_project_iam_binding` or `_policy`, and do not grant basic roles.
The checks will catch both.

## Step 4 — Output (R2.8)

Add an output `web_service_account_email`. Lesson 3 will attach this account to a VM.

## Reflection questions

1. A colleague grants `roles/logging.logWriter` to their own CI account through the console. Then you apply a `google_project_iam_binding` for the same role. What happens to their grant?
2. Why `depends_on` on the service account, but *not* on the IAM members?
3. The IAM members reference the account's `email`, which is unknown until apply. How does Terraform still produce a plan?
