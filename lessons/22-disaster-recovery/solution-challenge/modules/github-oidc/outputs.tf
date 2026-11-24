output "workload_identity_provider" {
  description = "Full provider name for google-github-actions/auth (workload_identity_provider)."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "plan_service_account_email" {
  description = "Read-only identity used by pull-request plans."
  value       = google_service_account.plan.email
}
