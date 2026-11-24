locals {
  common_labels = {
    app        = "meridian"
    env        = var.environment
    managed_by = "terraform"
  }
}

# Bucket names are global across all of Google Cloud, so add a random suffix.
resource "random_id" "bucket_suffix" {
  byte_length = 3
}

resource "google_storage_bucket" "assets" {
  name          = "${var.project_id}-assets-${random_id.bucket_suffix.hex}"
  location      = upper(var.region)
  storage_class = "STANDARD"

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  versioning {
    enabled = true
  }

  # Old object versions are kept for 30 days, then deleted.
  lifecycle_rule {
    condition {
      days_since_noncurrent_time = 30
    }
    action {
      type = "Delete"
    }
  }

  labels = local.common_labels
}

data "google_client_config" "current" {}
