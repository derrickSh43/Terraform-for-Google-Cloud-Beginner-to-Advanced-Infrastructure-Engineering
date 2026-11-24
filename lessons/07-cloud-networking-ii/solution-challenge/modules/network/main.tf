resource "google_compute_network" "this" {
  name                    = "${var.name_prefix}-vpc"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
}

resource "google_compute_subnetwork" "this" {
  for_each = var.subnets

  name                     = "${var.name_prefix}-${each.key}"
  region                   = var.region
  network                  = google_compute_network.this.id
  ip_cidr_range            = each.value
  private_ip_google_access = true
}

resource "google_compute_router" "this" {
  count = var.enable_nat ? 1 : 0

  name    = "${var.name_prefix}-router"
  region  = var.region
  network = google_compute_network.this.id
}

# Reserved addresses: partners can allowlist exactly these egress IPs.
resource "google_compute_address" "nat" {
  count = var.enable_nat ? var.nat_ip_count : 0

  name         = "${var.name_prefix}-nat-${count.index}"
  region       = var.region
  address_type = "EXTERNAL"
}

resource "google_compute_router_nat" "this" {
  count = var.enable_nat ? 1 : 0

  name   = "${var.name_prefix}-nat"
  router = google_compute_router.this[0].name
  region = var.region

  nat_ip_allocate_option = var.nat_ip_count > 0 ? "MANUAL_ONLY" : "AUTO_ONLY"
  nat_ips                = google_compute_address.nat[*].self_link

  # Only the listed (private) tiers get NAT; everything else has no path out.
  source_subnetwork_ip_ranges_to_nat = length(var.nat_subnets) > 0 ? "LIST_OF_SUBNETWORKS" : "ALL_SUBNETWORKS_ALL_IP_RANGES"

  dynamic "subnetwork" {
    for_each = var.nat_subnets
    content {
      name                    = google_compute_subnetwork.this[subnetwork.value].id
      source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
    }
  }

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}
