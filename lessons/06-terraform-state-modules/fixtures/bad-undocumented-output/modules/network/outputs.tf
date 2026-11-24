output "network_id" {
  description = "ID of the VPC network."
  value       = google_compute_network.this.id
}

output "subnet_ids" {
  value       = { for k, s in google_compute_subnetwork.this : k => s.id }
}
