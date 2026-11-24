resource "google_service_account_key" "ci" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${module.ci.email}"
}
