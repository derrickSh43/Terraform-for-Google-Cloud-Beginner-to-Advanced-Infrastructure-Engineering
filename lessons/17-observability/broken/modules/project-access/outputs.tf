output "grant_keys" {
  description = "principal + role pairs granted by this module."
  value       = keys(local.grants)
}
