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
}
