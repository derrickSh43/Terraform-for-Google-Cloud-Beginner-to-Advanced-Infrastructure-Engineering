output "zone" {
  description = "DNS peering zone name."
  value       = google_dns_managed_zone.this.name
}
