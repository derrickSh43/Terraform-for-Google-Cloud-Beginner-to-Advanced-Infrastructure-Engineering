output "bucket_name" {
  description = "Name of the static assets bucket."
  value       = google_storage_bucket.assets.name
}

output "bucket_url" {
  description = "gs:// URL of the static assets bucket."
  value       = google_storage_bucket.assets.url
}

output "active_project" {
  description = "Project the Google provider is configured for."
  value       = data.google_client_config.current.project
}

output "web_service_account_email" {
  description = "Email of the web tier service account."
  value       = google_service_account.web.email
}
