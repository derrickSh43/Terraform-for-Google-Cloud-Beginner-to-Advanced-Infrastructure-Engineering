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

  labels = var.labels
}

data "google_client_config" "current" {}
