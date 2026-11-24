# Static assets (book covers, CSS, images) for the Meridian Books storefront.
resource "google_storage_bucket" "assets" {
  name     = "${var.project_id}-assets"
  location = upper(var.region)

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  versioning {
    enabled = false
  }

  labels = {
    app        = "meridian"
    env        = var.environment
    managed_by = "terraform"
  }
}

# Reads the provider's own configuration. Resolves locally - no API call needed.
data "google_client_config" "current" {}
