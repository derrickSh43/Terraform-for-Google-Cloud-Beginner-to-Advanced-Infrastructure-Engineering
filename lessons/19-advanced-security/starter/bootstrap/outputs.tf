output "state_bucket" {
  description = "Bucket name to use in every backend \"gcs\" block."
  value       = google_storage_bucket.tfstate.name
}
