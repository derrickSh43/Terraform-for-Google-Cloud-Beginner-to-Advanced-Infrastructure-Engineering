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

output "enabled_apis" {
  description = "APIs enabled by this module. Depend on this output to wait for them."
  value       = [for s in google_project_service.apis : s.service]
}

output "backups_bucket" {
  description = "Name of the backups bucket."
  value       = google_storage_bucket.backups.name
}
