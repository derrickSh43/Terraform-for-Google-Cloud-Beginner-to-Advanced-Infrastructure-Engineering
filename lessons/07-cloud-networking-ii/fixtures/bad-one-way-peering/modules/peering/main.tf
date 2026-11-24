# VPC peering is two one-way connections. It only becomes ACTIVE once both
# sides exist, and the two networks' subnet ranges must not overlap.

resource "google_compute_network_peering" "a_to_b" {
  name         = var.name_a_to_b
  network      = var.network_a_id
  peer_network = var.network_b_id

  # Share only subnet routes - no custom (static/BGP) routes leak across.
  export_custom_routes = false
  import_custom_routes = false
}

