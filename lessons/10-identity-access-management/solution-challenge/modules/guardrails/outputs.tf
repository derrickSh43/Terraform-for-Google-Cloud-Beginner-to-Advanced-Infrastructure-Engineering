output "policies" {
  description = "Organization policies enforced on the project."
  value       = [google_org_policy_policy.no_sa_keys.name]
}
