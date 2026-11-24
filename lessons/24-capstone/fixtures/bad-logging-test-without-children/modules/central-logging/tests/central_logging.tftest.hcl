# Tests for modules/central-logging (capstone).
mock_provider "google" {}

variables {
  folder             = "folders/123"
  logging_project_id = "meridian-logging-ab12"
}

run "collects_every_child_project" {
  command = plan

  assert {
    condition     = google_logging_folder_sink.central.name == "meridian-central"
    error_message = "The sink has a stable name."
  }

  assert {
    condition     = google_logging_folder_sink.central.folder == "folders/123"
    error_message = "The sink belongs to the folder it collects from."
  }

  assert {
    condition     = google_project_iam_member.sink_writer.role == "roles/logging.bucketWriter" && google_project_iam_member.sink_writer.project == "meridian-logging-ab12"
    error_message = "The sink's identity needs bucketWriter in the logging project."
  }
}

run "keeps_logs_long_enough" {
  command = plan

  assert {
    condition     = google_logging_project_bucket_config.central.retention_days >= 365
    error_message = "Central logs are kept at least a year by default."
  }
}
