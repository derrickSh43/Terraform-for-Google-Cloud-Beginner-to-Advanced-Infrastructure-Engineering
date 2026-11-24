output "ip_address" {
  description = "Internal IP that Google API traffic should resolve to."
  value       = google_compute_global_address.this.address
}
