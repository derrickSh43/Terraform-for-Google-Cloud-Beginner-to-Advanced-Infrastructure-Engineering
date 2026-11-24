output "service_account_email" {
  description = "Email of the workload's service account."
  value       = google_service_account.this.email
}

output "internal_ip" {
  description = "Primary internal IP of the VM."
  value       = google_compute_instance.this.network_interface[0].network_ip
}

output "external_ip" {
  description = "Ephemeral public IP, or null when external_ip = false."
  value       = try(google_compute_instance.this.network_interface[0].access_config[0].nat_ip, null)
}
