# Every log entry from every project under the Meridian folder is copied to one
# log bucket in the logging project: one place to search, one retention policy,
# and project owners can't delete the copy.

resource "google_logging_project_bucket_config" "central" {
  project        = var.logging_project_id
  location       = "global"
  bucket_id      = "meridian-central"
  retention_days = var.retention_days
}

resource "google_logging_folder_sink" "central" {
  name             = "meridian-central"
  folder           = var.folder
  include_children = true
  destination      = "logging.googleapis.com/${google_logging_project_bucket_config.central.id}"

  # FinOps: health-check and load balancer access logs are most of the volume
  # and almost never read. Keep them in each project's default bucket only.
  exclusions {
    name   = "lb-requests"
    filter = "resource.type=\"http_load_balancer\" AND httpRequest.status<400"
  }
}

# The sink writes with its own identity, which needs permission on the bucket's project.
resource "google_project_iam_member" "sink_writer" {
  project = var.logging_project_id
  role    = "roles/logging.bucketWriter"
  member  = google_logging_folder_sink.central.writer_identity
}
