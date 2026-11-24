# The app tier is private: no external IP, reachable only from the web tier
# (and IAP for administration).

resource "google_compute_subnetwork" "app" {
  name                     = "meridian-${var.environment}-app"
  region                   = var.region
  network                  = google_compute_network.main.id
  ip_cidr_range            = var.app_subnet_cidr
  private_ip_google_access = true
}

resource "google_service_account" "app" {
  account_id   = "meridian-app"
  display_name = "Meridian app tier"
  description  = "Runs the Meridian API VMs."

  depends_on = [google_project_service.apis]
}

resource "google_project_iam_member" "app" {
  for_each = local.web_roles # same needs as web: write logs and metrics

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.app.email}"
}

resource "google_compute_instance" "app" {
  name         = "meridian-app-1"
  machine_type = "e2-micro"
  zone         = var.zone

  tags = ["app"]

  labels = {
    app        = "meridian"
    env        = var.environment
    managed_by = "terraform"
    role       = "app"
  }

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 10
      type  = "pd-balanced"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.app.id
    access_config {}
  }

  metadata = {
    enable-oslogin = "TRUE"
  }

  metadata_startup_script = file("${path.module}/scripts/app-startup.sh")

  service_account {
    email  = google_service_account.app.email
    scopes = ["cloud-platform"]
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  depends_on = [
    google_project_service.apis,
    google_project_iam_member.app,
  ]
}
