# VPC Service Controls in dry-run: violations are logged, not blocked, until the
# perimeter is proven not to break legitimate traffic.
resource "google_access_context_manager_service_perimeter" "data" {
  parent = "accessPolicies/${var.access_policy_id}"
  name   = "accessPolicies/${var.access_policy_id}/servicePerimeters/${var.name}"
  title  = var.name

  use_explicit_dry_run_spec = true

  spec {
    resources           = ["projects/${var.project_number}"]
    restricted_services = var.restricted_services
  }
}
