# Project-level building blocks every environment needs: APIs and the
# static-assets bucket (lessons 01-02).

resource "google_project_service" "apis" {
  for_each = var.apis

  service = each.value

  # Never switch an API off just because this config is destroyed.
  disable_on_destroy = false
}

resource "google_storage_bucket" "assets" {
  name     = "${var.project_id}-assets"
  location = upper(var.region)

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  versioning {
    enabled = true
  }

  # Overwritten or deleted assets are kept 30 days, then removed.
  lifecycle_rule {
    condition {
      days_since_noncurrent_time = 30
    }
    action {
      type = "Delete"
    }
  }

  labels = var.labels
}

# Application backups (database dumps from lesson 12, exports). Objects can't be
# deleted or overwritten until they are var.backup_retention_days old - not even
# by an admin. They get cheaper as they age, and expire after a year.
resource "google_storage_bucket" "backups" {
  name          = "${var.project_id}-backups"
  location      = upper(var.region)
  storage_class = "STANDARD"

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false


  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type = "Delete"
    }
  }

  labels = merge(var.labels, { purpose = "backups" })
}

data "google_client_config" "current" {}
