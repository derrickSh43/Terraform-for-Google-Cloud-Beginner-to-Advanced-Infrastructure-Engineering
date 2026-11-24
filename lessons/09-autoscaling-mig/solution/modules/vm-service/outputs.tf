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

output "self_link" {
  description = "Self link of the VM, for instance groups and load balancer backends."
  value       = google_compute_instance.this.self_link
}

output "zone" {
  description = "Zone the VM runs in."
  value       = google_compute_instance.this.zone
}
