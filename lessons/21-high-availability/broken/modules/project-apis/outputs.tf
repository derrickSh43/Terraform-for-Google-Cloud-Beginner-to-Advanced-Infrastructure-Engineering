output "enabled" {
  description = "Enabled API names."
  value       = [for s in google_project_service.this : s.service]
}
