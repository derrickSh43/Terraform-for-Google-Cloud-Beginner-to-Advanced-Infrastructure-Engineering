# One workload = one identity + its roles + one VM.
# Used twice: the public web tier and the private app tier.

resource "google_service_account" "this" {
  account_id   = "meridian-${var.name}"
  display_name = var.display_name
  description  = var.description
}

resource "google_project_iam_member" "this" {
  for_each = var.roles

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.this.email}"
}

resource "google_compute_instance" "this" {
  name         = "meridian-${var.name}-01"
  machine_type = var.machine_type
  zone         = var.zone

  tags   = [var.name]
  labels = merge(var.labels, { role = var.name })

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 10
      type  = "pd-balanced"
    }
  }

  network_interface {
    subnetwork = var.subnet_id

    dynamic "access_config" {
      for_each = var.external_ip ? [1] : []
      content {}
    }
  }

  metadata = {
    enable-oslogin = "TRUE"
  }

  metadata_startup_script = var.startup_script

  service_account {
    email  = google_service_account.this.email
    scopes = ["cloud-platform"]
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  depends_on = [google_project_iam_member.this]
}
