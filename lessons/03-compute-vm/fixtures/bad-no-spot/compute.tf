resource "google_compute_instance" "web" {
  name         = "meridian-web-1"
  machine_type = var.machine_type
  zone         = var.zone

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
    enable-oslogin         = "TRUE"
    block-project-ssh-keys = "TRUE"
  }

  metadata_startup_script = templatefile("${path.module}/scripts/startup.sh.tftpl", {
    environment = var.environment
  })


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
