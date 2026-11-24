output "project_ids" {
  description = "Project name => project ID."
  value       = { for k, p in google_project.this : k => p.project_id }
}
