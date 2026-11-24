# Private container registry for Meridian images, with automatic cleanup.

resource "google_artifact_registry_repository" "this" {
  repository_id = var.repository_id
  location      = var.region
  format        = "DOCKER"
  description   = "Meridian container images."
  labels        = var.labels

  cleanup_policy_dry_run = false

}

# Repository-level IAM: CI can push images here, nowhere else.
resource "google_artifact_registry_repository_iam_member" "writers" {
  for_each = toset(var.writers)

  location   = google_artifact_registry_repository.this.location
  repository = google_artifact_registry_repository.this.name
  role       = "roles/artifactregistry.writer"
  member     = each.value
}
