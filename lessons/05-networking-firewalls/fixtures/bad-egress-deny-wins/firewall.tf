# A VPC starts with two implied rules: deny all ingress, allow all egress.
# Each rule below opens (or closes) exactly one path in the connectivity matrix.

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

  log_config {
    metadata = "INCLUDE_ALL_METADATA"
  }
}

resource "google_compute_firewall" "allow_iap_ssh" {
  name        = "meridian-${var.environment}-allow-iap-ssh"
  description = "SSH only through Identity-Aware Proxy TCP forwarding."
  network     = google_compute_network.main.id
  direction   = "INGRESS"
  priority    = 1000

  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["web", "app"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  log_config {
    metadata = "INCLUDE_ALL_METADATA"
  }
}

# Service accounts instead of tags: anyone with instance-admin rights can add a
# tag to a VM, but attaching a service account also requires
# iam.serviceAccountUser on that account.
resource "google_compute_firewall" "allow_web_to_app" {
  name        = "meridian-${var.environment}-allow-web-to-app"
  description = "Web tier identity calls the API identity on 8080."
  network     = google_compute_network.main.id
  direction   = "INGRESS"
  priority    = 1000

  source_service_accounts = [google_service_account.web.email]
  target_service_accounts = [google_service_account.app.email]

  allow {
    protocol = "tcp"
    ports    = ["8080"]
  }

  log_config {
    metadata = "INCLUDE_ALL_METADATA"
  }
}

# --- Egress lockdown for the app tier ---------------------------------------

resource "google_compute_firewall" "app_allow_google_apis" {
  name        = "meridian-${var.environment}-app-allow-google-apis"
  description = "App tier may reach Google APIs via private.googleapis.com only."
  network     = google_compute_network.main.id
  direction   = "EGRESS"
  priority    = 1000

  destination_ranges      = ["199.36.153.8/30"]
  target_service_accounts = [google_service_account.app.email]

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }

  log_config {
    metadata = "INCLUDE_ALL_METADATA"
  }
}

resource "google_compute_firewall" "app_deny_all_egress" {
  name        = "meridian-${var.environment}-app-deny-egress"
  description = "Everything else leaving the app tier is denied."
  network     = google_compute_network.main.id
  direction   = "EGRESS"
  priority    = 500

  destination_ranges      = ["0.0.0.0/0"]
  target_service_accounts = [google_service_account.app.email]

  deny {
    protocol = "all"
  }

  log_config {
    metadata = "INCLUDE_ALL_METADATA"
  }
}
