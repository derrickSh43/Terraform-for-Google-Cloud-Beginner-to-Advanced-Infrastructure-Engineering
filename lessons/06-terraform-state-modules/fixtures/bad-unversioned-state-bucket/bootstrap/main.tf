# Bootstrap: the bucket that stores every other configuration's state.
#
# Chicken-and-egg: this configuration can't keep its own state in a bucket
# that doesn't exist yet, so it uses local state (commit-free, kept safe by the
# platform team) or is migrated into the bucket after the first apply.

resource "google_storage_bucket" "tfstate" {
  name     = "${var.project_id}-tfstate"
  location = upper(var.region)

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  # Every state write keeps the previous version: your undo button.
  versioning {
    enabled = false
  }

  # ...but don't keep thousands of old versions forever.
  lifecycle_rule {
    condition {
      num_newer_versions = 20
      with_state         = "ARCHIVED"
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    app        = "meridian"
    purpose    = "terraform-state"
    managed_by = "terraform"
  }

  lifecycle {
    prevent_destroy = true
  }
}
