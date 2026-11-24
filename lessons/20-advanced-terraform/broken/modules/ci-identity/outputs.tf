output "email" {
  description = "Email of the CI service account (use with impersonate_service_account)."
  value       = google_service_account.this.email
}

output "deployer_role_id" {
  description = "Full ID of the custom deployer role."
  value       = google_project_iam_custom_role.deployer.id
}
