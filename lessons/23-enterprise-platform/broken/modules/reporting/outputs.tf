output "reports_bucket" {
  description = "Bucket the nightly job writes reports to."
  value       = google_storage_bucket.reports.name
}

output "archive_bucket" {
  description = "Long-term report archive."
  value       = google_storage_bucket.archive.name
}

output "reporter_email" {
  description = "Service account the nightly job runs as."
  value       = google_service_account.reporter.email
}
