output "network_id" {
  description = "ID of the VPC network."
  value       = google_compute_network.this.id
}

output "subnet_ids" {
  description = "Subnet IDs keyed by tier name."
  value       = { for k, s in google_compute_subnetwork.this : k => s.id }
}

output "nat_name" {
  description = "Name of the Cloud NAT gateway, or null when enable_nat = false."
  value       = one(google_compute_router_nat.this[*].name)
}
