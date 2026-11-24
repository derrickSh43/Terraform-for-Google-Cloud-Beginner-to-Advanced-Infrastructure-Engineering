# One direction of a VPC peering. The other half lives in the other network's
# configuration (often another team's repository).
resource "google_compute_network_peering" "this" {
  name                 = var.name
  network              = var.network_id
  peer_network         = var.peer_network_id
  import_custom_routes = var.import_custom_routes
  export_custom_routes = var.export_custom_routes
}
