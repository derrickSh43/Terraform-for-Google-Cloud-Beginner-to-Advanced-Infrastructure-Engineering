output "meridian_folder" {
  description = "The top Meridian folder (folders/<id>)."
  value       = google_folder.meridian.name
}

output "env_folders" {
  description = "Environment => folder (folders/<id>)."
  value       = { for k, f in google_folder.env : k => f.name }
}
