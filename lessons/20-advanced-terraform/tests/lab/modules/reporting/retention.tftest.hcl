# Runs inside modules/reporting.
mock_provider "google" {}

variables {
  project_id  = "test-project"
  name_prefix = "meridian-test"
  region      = "us-central1"
  labels      = { team = "reporting" }
}

run "defaults_plan_cleanly" {
  command = plan

  assert {
    condition     = google_storage_bucket.reports.name == "meridian-test-sales-reports"
    error_message = "Bucket names must come from var.name_prefix."
  }

  assert {
    condition     = google_storage_bucket.reports.project == "test-project" && google_storage_bucket.archive.project == "test-project"
    error_message = "Every bucket must be created in var.project_id."
  }

  assert {
    condition     = google_storage_bucket.reports.location == "US-CENTRAL1"
    error_message = "Buckets live in var.region."
  }
}

run "one_week_retention_rejected" {
  command = plan

  variables {
    retention_days = 7
  }

  expect_failures = [var.retention_days]
}

run "three_year_retention_rejected" {
  command = plan

  variables {
    retention_days = 1095
  }

  expect_failures = [var.retention_days]
}
