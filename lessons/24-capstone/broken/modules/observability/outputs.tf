output "notification_channel" {
  description = "On-call notification channel ID (reuse it for new alerts)."
  value       = google_monitoring_notification_channel.oncall.id
}

output "audit_bucket" {
  description = "Bucket receiving audit logs."
  value       = google_storage_bucket.audit.name
}
