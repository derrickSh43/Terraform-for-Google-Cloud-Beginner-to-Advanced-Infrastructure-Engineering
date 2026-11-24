output "ip_address" {
  description = "Public IP address of the load balancer."
  value       = google_compute_global_address.this.address
}

output "backend_service_id" {
  description = "ID of the backend service (for monitoring and Cloud Armor later)."
  value       = google_compute_backend_service.this.id
}
