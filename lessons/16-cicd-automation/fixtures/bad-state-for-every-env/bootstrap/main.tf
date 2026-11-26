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
    enabled = true
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

# --- Who may use which state (lesson 16) --------------------------------------
# Each environment's CI identities live in that environment's project. The plan identity
# may read its environment's state; the apply identity may also write it (state and lock
# file). The condition keeps dev's identities out of prod's state and the other way round.
# Allowing the bucket itself (resource.type) lets them list object names, which the gcs
# backend needs; reading or writing an object still requires the envs/<env>/ prefix.
locals {
  state_access = merge([
    for env, project in var.ci_projects : {
      "${env}-plan" = {
        env    = env
        role   = "roles/storage.objectViewer"
        member = "serviceAccount:meridian-ci-plan@${project}.iam.gserviceaccount.com"
      }
      "${env}-apply" = {
        env    = env
        role   = "roles/storage.objectUser"
        member = "serviceAccount:meridian-ci-apply@${project}.iam.gserviceaccount.com"
      }
    }
  ]...)
}

resource "google_storage_bucket_iam_member" "ci_state" {
  for_each = local.state_access

  bucket = google_storage_bucket.tfstate.name
  role   = each.value.role
  member = each.value.member

}
