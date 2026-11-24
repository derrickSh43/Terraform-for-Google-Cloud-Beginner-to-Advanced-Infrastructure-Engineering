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
  name         = "meridian-${var.name}-1"
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

  # The data disk is attached by google_compute_attached_disk below. Without this,
  # every plan would try to detach it again (two resources managing one setting).
  lifecycle {
    ignore_changes = [attached_disk]
  }

  depends_on = [google_project_iam_member.this]
}

# --- Persistent data ---------------------------------------------------------
# A separate disk outlives the VM: recreate the VM (new image, new machine type)
# and the data stays.

locals {
  region = join("-", slice(split("-", var.zone), 0, 2))
}

resource "google_compute_disk" "data" {
  count = var.data_disk_size_gb > 0 ? 1 : 0

  name   = "meridian-${var.name}-data"
  zone   = var.zone
  type   = "pd-balanced"
  size   = var.data_disk_size_gb
  labels = merge(var.labels, { role = var.name, data = "true" })

  lifecycle {
    prevent_destroy = true # data loss is not a plan you should be able to approve by accident
  }
}

resource "google_compute_attached_disk" "data" {
  count = var.data_disk_size_gb > 0 ? 1 : 0

  disk        = google_compute_disk.data[0].id
  instance    = google_compute_instance.this.id
  device_name = "data"
}

# Daily snapshots, kept for var.snapshot_retention_days.
resource "google_compute_resource_policy" "snapshots" {
  count = var.data_disk_size_gb > 0 ? 1 : 0

  name   = "meridian-${var.name}-daily-snapshots"
  region = local.region

  snapshot_schedule_policy {
    schedule {
      daily_schedule {
        days_in_cycle = 1
        start_time    = "03:00" # UTC, outside shopping hours
      }
    }

    retention_policy {
      max_retention_days    = var.snapshot_retention_days
      on_source_disk_delete = "APPLY_RETENTION_POLICY" # if the disk is ever deleted, the backups survive
    }
  }
}

resource "google_compute_disk_resource_policy_attachment" "snapshots" {
  count = var.data_disk_size_gb > 0 ? 1 : 0

  name = google_compute_resource_policy.snapshots[0].name
  disk = google_compute_disk.data[0].name
  zone = var.zone
}

# Object-level write access to named buckets (e.g. backups). Bucket-level, never project-level.
resource "google_storage_bucket_iam_member" "writer" {
  for_each = toset(var.writable_buckets)

  bucket = each.value
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.this.email}"
}
