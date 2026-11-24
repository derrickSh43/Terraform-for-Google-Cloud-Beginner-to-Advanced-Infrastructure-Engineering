output "slo_id" {
  description = "ID of the availability SLO."
  value       = google_monitoring_slo.availability.id
}
