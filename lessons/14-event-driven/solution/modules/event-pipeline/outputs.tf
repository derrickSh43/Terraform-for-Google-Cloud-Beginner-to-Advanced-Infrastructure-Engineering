output "topic_id" {
  description = "ID of the events topic."
  value       = google_pubsub_topic.events.id
}

output "push_service_account_email" {
  description = "Identity Pub/Sub uses when pushing to the worker (grant it run.invoker)."
  value       = google_service_account.push.email
}

output "dead_letter_subscription" {
  description = "Pull subscription for inspecting failed messages."
  value       = google_pubsub_subscription.dead_letter.name
}
