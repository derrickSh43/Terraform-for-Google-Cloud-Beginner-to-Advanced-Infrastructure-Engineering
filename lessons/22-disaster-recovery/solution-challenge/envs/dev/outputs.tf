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
  description = "Internal load balancer address of the API (no external IP exists)."
  value       = module.app_lb.ip_address
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

output "backups_bucket" {
  description = "Bucket for application backups (retention-protected)."
  value       = module.foundation.backups_bucket
}

output "db_connection_name" {
  description = "Cloud SQL connection name for the app's connector."
  value       = module.db.connection_name
}

output "db_password_secret" {
  description = "Secret Manager secret with the database password (read it with the app's identity)."
  value       = module.db.password_secret_id
}

output "image_repository" {
  description = "Push images here (CI has writer access)."
  value       = module.registry.repository_url
}

output "orders_topic" {
  description = "Publish order events here."
  value       = module.orders.topic_id
}

output "orders_dead_letters" {
  description = "Inspect failed order events with this pull subscription."
  value       = module.orders.dead_letter_subscription
}

output "batch_cluster" {
  description = "GKE cluster for batch jobs (private endpoint: connect from the ops VPC)."
  value       = module.batch_cluster.cluster_name
}

output "github_workload_identity_provider" {
  description = "Set as the WIF_PROVIDER repository variable in GitHub."
  value       = module.github.workload_identity_provider
}

output "github_plan_service_account" {
  description = "Set as PLAN_SERVICE_ACCOUNT in GitHub."
  value       = module.github.plan_service_account_email
}

output "github_apply_service_account" {
  description = "Set as the APPLY_SERVICE_ACCOUNT variable in GitHub."
  value       = module.github.apply_service_account_email
}

output "failover_commands" {
  description = "What to run if the primary region is lost (see the DR runbook)."
  value = var.dr_region == null ? [] : [
    "gcloud sql instances promote-replica ${module.db.replica_name} --project=${var.project_id}",
    "terraform apply -var region=${var.dr_region} -var 'web_zones=[\"${var.dr_region}-b\",\"${var.dr_region}-c\",\"${var.dr_region}-d\"]'  # rebuild compute in ${var.dr_region}",
  ]
}
