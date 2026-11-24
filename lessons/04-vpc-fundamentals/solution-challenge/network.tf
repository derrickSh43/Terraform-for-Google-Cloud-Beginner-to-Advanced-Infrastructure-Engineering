resource "google_compute_network" "main" {
  name                    = "meridian-${var.environment}-vpc"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"

  depends_on = [google_project_service.apis]
}

# One subnet per entry in var.subnets - add a tier by adding a map entry.
resource "google_compute_subnetwork" "tier" {
  for_each = var.subnets

  name                     = "meridian-${var.environment}-${each.key}"
  region                   = var.region
  network                  = google_compute_network.main.id
  ip_cidr_range            = each.value
  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}
