output "policy_id" {
  description = "Security policy to attach to backend services."
  value       = google_compute_security_policy.this.id
}
