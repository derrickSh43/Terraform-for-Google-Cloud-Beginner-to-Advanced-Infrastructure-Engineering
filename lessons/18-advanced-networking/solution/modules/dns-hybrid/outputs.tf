output "corp_zone" {
  description = "Forwarding zone name."
  value       = google_dns_managed_zone.corp.name
}
