output "peering_names" {
  description = "Names of both halves of the peering."
  value       = [google_compute_network_peering.a_to_b.name, google_compute_network_peering.b_to_a.name]
}
