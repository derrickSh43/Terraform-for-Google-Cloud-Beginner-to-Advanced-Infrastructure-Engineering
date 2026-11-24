output "bucket_name" {
  description = "Name of the static assets bucket."
  value       = module.foundation.bucket_name
}

output "bucket_url" {
  description = "gs:// URL of the static assets bucket."
  value       = module.foundation.bucket_url
}

output "active_project" {
  description = "Project the Google provider is configured for."
  value       = module.foundation.active_project
}

output "web_service_account_email" {
  description = "Email of the web tier service account."
  value       = module.web.service_account_email
}

output "web_external_ip" {
  description = "Ephemeral public IP of the web VM."
  value       = module.web.external_ip
}

output "web_url" {
  description = "URL of the Meridian storefront."
  value       = "http://${module.web.external_ip}"
}

output "vpc_id" {
  description = "ID of the Meridian VPC."
  value       = module.network.network_id
}

output "web_subnet_id" {
  description = "ID of the web subnet."
  value       = module.network.subnet_ids["web"]
}

output "app_internal_ip" {
  description = "Internal IP of the app VM (no external IP exists)."
  value       = module.app.internal_ip
}
