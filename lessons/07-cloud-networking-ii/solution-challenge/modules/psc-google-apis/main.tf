# Private Service Connect endpoint: Google APIs on an internal IP inside your VPC.
resource "google_compute_global_address" "this" {
  name         = "${var.name}-ip"
  purpose      = "PRIVATE_SERVICE_CONNECT"
  address_type = "INTERNAL"
  network      = var.network_id
  address      = var.ip_address
}

resource "google_compute_global_forwarding_rule" "this" {
  name                  = var.name # 1-20 lowercase letters/digits, no hyphens
  target                = "all-apis"
  network               = var.network_id
  ip_address            = google_compute_global_address.this.id
  load_balancing_scheme = ""
}
