# Keyless CI: GitHub Actions exchanges its own OIDC token for a short-lived
# Google token. Two identities with different power:
#   * plan  (read-only)  - any branch / pull request of the repository
#   * apply (meridian-ci) - only workflows running on refs/heads/main

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = var.pool_id
  display_name              = "GitHub Actions"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }


  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# --- Plan identity: sees everything, changes nothing -------------------------
resource "google_service_account" "plan" {
  account_id   = "meridian-ci-plan"
  display_name = "CI plan (read-only)"
}

resource "google_project_iam_member" "plan" {
  for_each = toset(var.plan_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.plan.email}"
}

resource "google_service_account_iam_member" "plan_from_repository" {
  service_account_id = google_service_account.plan.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.repository}"
}

# --- Apply identity: only from main -------------------------------------------
resource "google_service_account_iam_member" "apply_from_main" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${var.apply_service_account_email}"
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.ref/refs/heads/main"
}
