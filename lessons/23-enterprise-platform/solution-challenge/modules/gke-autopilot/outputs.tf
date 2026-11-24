output "cluster_name" {
  description = "Name of the cluster."
  value       = google_container_cluster.this.name
}

output "node_service_account" {
  description = "Service account the nodes run as."
  value       = google_service_account.nodes.email
}

output "workload_service_accounts" {
  description = "Google service accounts for Kubernetes workloads (annotate the KSAs with these)."
  value       = { for k, sa in google_service_account.workload : k => sa.email }
}
