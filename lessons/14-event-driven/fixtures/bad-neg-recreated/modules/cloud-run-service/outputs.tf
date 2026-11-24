output "service_account_email" {
  description = "Identity the service runs as."
  value       = google_service_account.this.email
}

output "neg_id" {
  description = "Serverless NEG for a load balancer backend (null when create_neg = false)."
  value       = one([for n in google_compute_region_network_endpoint_group.this : n.id])
}

output "uri" {
  description = "HTTPS URL of the service (for Pub/Sub push or internal callers)."
  value       = google_cloud_run_v2_service.this.uri
}

output "service_name" {
  description = "Cloud Run service name."
  value       = google_cloud_run_v2_service.this.name
}
