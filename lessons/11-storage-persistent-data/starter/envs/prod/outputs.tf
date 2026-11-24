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

output "lb_ip" {
  description = "Public IP of the storefront load balancer."
  value       = module.lb.ip_address
}

output "web_url" {
  description = "URL of the Meridian storefront (through the load balancer)."
  value       = "http://${module.lb.ip_address}"
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

output "ops_vpc_id" {
  description = "ID of the peered operations VPC."
  value       = module.ops_network.network_id
}

output "nat_name" {
  description = "Cloud NAT gateway serving the main VPC."
  value       = module.network.nat_name
}

output "ci_service_account" {
  description = "Impersonate this account from CI or a terminal - there are no keys."
  value       = module.ci.email
}
