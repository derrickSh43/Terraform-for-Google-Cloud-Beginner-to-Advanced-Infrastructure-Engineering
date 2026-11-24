# Private container registry for Meridian images, with automatic cleanup.

resource "google_artifact_registry_repository" "this" {
  repository_id = var.repository_id
  location      = coalesce(var.location, var.region)
  format        = "DOCKER"
  description   = "Meridian container images."
  labels        = var.labels

  cleanup_policy_dry_run = false

  # Untagged images (superseded builds) are deleted after 30 days...
  cleanup_policies {
    id     = "delete-untagged"
    action = "DELETE"
    condition {
      tag_state  = "UNTAGGED"
      older_than = "2592000s"
    }
  }

  # ...but the 10 most recent versions of every image are always kept (rollback).
  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 10
    }
  }
}

# Repository-level IAM: CI can push images here, nowhere else.
resource "google_artifact_registry_repository_iam_member" "writers" {
  for_each = toset(var.writers)

  location   = google_artifact_registry_repository.this.location
  repository = google_artifact_registry_repository.this.name
  role       = "roles/artifactregistry.writer"
  member     = each.value
}

# Repository-level pull access (e.g. GKE node service accounts).
resource "google_artifact_registry_repository_iam_member" "readers" {
  for_each = toset(var.readers)

  location   = google_artifact_registry_repository.this.location
  repository = google_artifact_registry_repository.this.name
  role       = "roles/artifactregistry.reader"
  member     = each.value
}
