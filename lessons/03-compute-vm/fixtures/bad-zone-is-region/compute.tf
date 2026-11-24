resource "google_compute_instance" "web" {
  name         = "meridian-web-1"
  machine_type = "e2-micro"
  zone         = var.region

  tags = ["web"]

  labels = {
    app        = "meridian"
    env        = var.environment
    managed_by = "terraform"
    role       = "web"
  }

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 10
      type  = "pd-balanced"
    }
  }

  # Lesson 4 moves this VM into a custom VPC.
  network_interface {
    network = "default"

    access_config {} # ephemeral external IP
  }

  metadata = {
    enable-oslogin = "TRUE"
  }

  metadata_startup_script = file("${path.module}/scripts/startup.sh")

  service_account {
    email  = google_service_account.web.email
    scopes = ["cloud-platform"] # IAM roles, not scopes, limit what the VM can do
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  depends_on = [
    google_project_service.apis,
    google_project_iam_member.web,
  ]
}
