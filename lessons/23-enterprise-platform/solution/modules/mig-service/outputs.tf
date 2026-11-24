output "service_account_email" {
  description = "Email of the workload's service account."
  value       = google_service_account.this.email
}

output "instance_group" {
  description = "Instance group URL of the MIG, for load balancer backends."
  value       = google_compute_region_instance_group_manager.this.instance_group
}

output "template_id" {
  description = "ID of the current instance template."
  value       = google_compute_instance_template.this.id
}
