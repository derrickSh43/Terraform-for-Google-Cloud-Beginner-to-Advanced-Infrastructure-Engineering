# Answer — Troubleshooting 10

**Symptom:** R10.6: `Project-level impersonation roles let principals act as EVERY service account`.

**Root cause:** `modules/ci-identity/main.tf` grants
`roles/iam.serviceAccountTokenCreator` with a **`google_project_iam_member`**. A role
granted on the project applies to every resource of that type in the project,
so the platform group can mint tokens for `meridian-ci`, `meridian-web`,
`meridian-app`, and any service account created in future. Through them it can
reach everything those accounts can. If any account holds a powerful role, the
group effectively holds it too.

**Fix:** grant the role on the account:

```hcl
resource "google_service_account_iam_member" "impersonators" {
  for_each = toset(var.impersonators)

  service_account_id = google_service_account.this.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = each.value
}
```

**Same trap:** `roles/iam.serviceAccountUser` (needed to attach an SA to a VM or
Cloud Run service) also applies to every account when granted at project level.
Grant it on specific accounts too.

**Lesson:** "who can do X" depends on the role **and** where it's attached.
Review IAM grants by scope, not just by role name.
