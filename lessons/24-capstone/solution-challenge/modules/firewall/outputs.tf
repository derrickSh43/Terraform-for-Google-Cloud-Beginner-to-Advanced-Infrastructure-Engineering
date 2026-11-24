output "rule_names" {
  description = "Names of the firewall rules created."
  value       = [for r in google_compute_firewall.this : r.name]
}
