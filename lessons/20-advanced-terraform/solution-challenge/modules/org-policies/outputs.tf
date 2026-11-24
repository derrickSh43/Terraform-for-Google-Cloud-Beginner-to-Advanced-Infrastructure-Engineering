output "policies" {
  description = "Enforced organization policy names."
  value       = concat([for p in google_org_policy_policy.enforced : p.name], [google_org_policy_policy.no_external_ips.name])
}
