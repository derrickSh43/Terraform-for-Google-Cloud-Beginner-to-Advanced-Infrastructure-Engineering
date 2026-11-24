# ---------------------------------------------------------------------------
# legacy-access.tf - created by hand during last spring's launch rush, then
# imported into Terraform so "at least it's in code". The security audit
# (lab.md, Part A) found every resource in this file. Lesson 10 replaces it.
# ---------------------------------------------------------------------------

# The CI pipeline's identity. The account itself is fine; how it's used is not.
resource "google_service_account" "ci" {
  account_id   = "meridian-ci"
  display_name = "CI pipeline"
}

# "It kept getting permission errors, so we gave it editor."
resource "google_project_iam_member" "ci_editor" {
  project = var.project_id
  role    = "roles/editor"
  member  = "serviceAccount:${google_service_account.ci.email}"
}

# A JSON key, pasted into the CI system's secret store (and a few laptops).
resource "google_service_account_key" "ci" {
  service_account_id = google_service_account.ci.name
}

# Authoritative: whoever applies this owns the *whole* logWriter member list.
resource "google_project_iam_binding" "log_writers" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  members = ["serviceAccount:meridian-web@meridian-dev-4821.iam.gserviceaccount.com"]
}

# The contractor left in March.
resource "google_project_iam_member" "contractor_owner" {
  project = var.project_id
  role    = "roles/owner"
  member  = "user:sam.contractor@example.com"
}

output "ci_key" {
  description = "CI key (base64). Copied into the CI secret store."
  value       = google_service_account_key.ci.private_key
  sensitive   = true
}
