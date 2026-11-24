output "project_ids" {
  description = "Projects created by the factory."
  value       = module.projects.project_ids
}

output "meridian_folder" {
  description = "Top folder of the landing zone."
  value       = module.landing_zone.meridian_folder
}
