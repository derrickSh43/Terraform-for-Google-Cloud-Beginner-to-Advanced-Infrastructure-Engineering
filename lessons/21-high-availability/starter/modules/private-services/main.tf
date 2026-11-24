# Private Service Access: Google-managed services (Cloud SQL, Memorystore...)
# run in a Google-owned VPC. This reserves an internal range in OUR network and
# peers it with that producer VPC, so the database gets an IP from our range
# and is reachable only over private networking.

resource "google_compute_global_address" "this" {
  name          = "${var.name_prefix}-psa"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  address       = var.range_address
  prefix_length = var.range_prefix_length
  network       = var.network_id
}

resource "google_service_networking_connection" "this" {
  network                 = var.network_id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.this.name]
}
