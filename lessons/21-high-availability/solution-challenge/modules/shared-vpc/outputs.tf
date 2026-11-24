output "service_projects" {
  description = "Attached service projects."
  value       = keys(google_compute_shared_vpc_service_project.this)
}
