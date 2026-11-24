resource "google_compute_network" "this" {
  name                    = "${var.name_prefix}-vpc"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
}

resource "google_compute_subnetwork" "this" {
  for_each = var.subnets

  name                     = "${var.name_prefix}-sub-${each.key}"
  region                   = var.region
  network                  = google_compute_network.this.id
  ip_cidr_range            = each.value
  private_ip_google_access = true

  # Alias IP ranges, e.g. pods and services for a VPC-native GKE cluster.
  dynamic "secondary_ip_range" {
    for_each = lookup(var.secondary_ranges, each.key, {})
    content {
      range_name    = secondary_ip_range.key
      ip_cidr_range = secondary_ip_range.value
    }
  }
}

# Outbound internet for VMs without external IPs (package installs, external APIs).
# Optional: count = 0 or 1 makes the whole router/NAT pair switchable per network.
resource "google_compute_router" "this" {
  count = var.enable_nat ? 1 : 0

  name    = "${var.name_prefix}-router"
  region  = var.region
  network = google_compute_network.this.id
}

resource "google_compute_router_nat" "this" {
  count = var.enable_nat ? 1 : 0

  name   = "${var.name_prefix}-nat"
  router = google_compute_router.this[0].name
  region = var.region

  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}
