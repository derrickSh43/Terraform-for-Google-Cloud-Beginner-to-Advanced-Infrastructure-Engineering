output "network_id" {
  description = "The network, read from the connection - depend on this so databases wait for the peering."
  value       = google_service_networking_connection.this.network
}

output "range_cidr" {
  description = "CIDR of the reserved managed-services range."
  value       = "${google_compute_global_address.this.address}/${google_compute_global_address.this.prefix_length}"
}
