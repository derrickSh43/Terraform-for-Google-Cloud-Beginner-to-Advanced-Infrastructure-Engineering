# A VPC starts with two implied rules: deny all ingress, allow all egress.
# Each rule below opens exactly one path in the connectivity matrix.

resource "google_compute_firewall" "allow_http" {
  name        = "meridian-${var.environment}-allow-http"
  description = "Public HTTP to the web tier."
  network     = google_compute_network.main.id
  direction   = "INGRESS"
  priority    = 1000

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["web"]

  allow {
    protocol = "tcp"
    ports    = ["80"]
  }
}

resource "google_compute_firewall" "allow_iap_ssh" {
  name        = "meridian-${var.environment}-allow-iap-ssh"
  description = "SSH only through Identity-Aware Proxy TCP forwarding."
  network     = google_compute_network.main.id
  direction   = "INGRESS"
  priority    = 1000

  source_ranges = ["35.235.240.0/20"] # IAP TCP forwarding range
  target_tags   = ["web", "app"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

resource "google_compute_firewall" "allow_web_to_app" {
  name        = "meridian-${var.environment}-allow-web-to-app"
  description = "Web tier calls the API on 8080."
  network     = google_compute_network.main.id
  direction   = "INGRESS"
  priority    = 1000

  source_tags = ["web"]
  target_tags = ["api"]

  allow {
    protocol = "tcp"
    ports    = ["8080"]
  }
}
