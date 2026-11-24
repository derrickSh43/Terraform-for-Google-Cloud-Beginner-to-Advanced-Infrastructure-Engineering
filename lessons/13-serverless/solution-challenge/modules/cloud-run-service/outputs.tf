output "service_account_email" {
  description = "Identity the service runs as."
  value       = google_service_account.this.email
}

output "neg_id" {
  description = "Serverless NEG for a load balancer backend."
  value       = google_compute_region_network_endpoint_group.this.id
}

output "service_name" {
  description = "Cloud Run service name."
  value       = google_cloud_run_v2_service.this.name
}
