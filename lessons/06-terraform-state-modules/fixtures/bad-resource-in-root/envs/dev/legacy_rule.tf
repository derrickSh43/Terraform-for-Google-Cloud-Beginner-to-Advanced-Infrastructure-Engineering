resource "google_compute_firewall" "temp_debug" {
  name    = "meridian-dev-temp-debug"
  network = module.network.network_id

  source_ranges = ["10.0.0.0/8"]
  target_tags   = ["app"]

  allow {
    protocol = "tcp"
    ports    = ["9090"]
  }
}
