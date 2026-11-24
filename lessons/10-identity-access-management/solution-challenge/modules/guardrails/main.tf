# Project-level organization policy: nobody can create service account keys,
# even with the permission. Keyless (impersonation / WIF) becomes the only way.
resource "google_org_policy_policy" "no_sa_keys" {
  name   = "projects/${var.project_id}/policies/iam.disableServiceAccountKeyCreation"
  parent = "projects/${var.project_id}"

  spec {
    rules {
      enforce = "TRUE"
    }
  }
}
