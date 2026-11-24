output "ip_address" {
  description = "Internal IP address clients connect to."
  value       = google_compute_forwarding_rule.this.ip_address
}

output "backend_service_id" {
  description = "ID of the regional backend service."
  value       = google_compute_region_backend_service.this.id
}
