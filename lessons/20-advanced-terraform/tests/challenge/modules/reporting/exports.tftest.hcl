# Runs inside modules/reporting.
mock_provider "google" {}

variables {
  project_id  = "test-project"
  name_prefix = "meridian-test"
  region      = "us-central1"
  labels      = { team = "reporting" }
}

run "one_bucket_per_quarter" {
  command = plan

  variables {
    export_quarters = ["2026-q1", "2026-q2"]
  }

  assert {
    condition     = length(google_storage_bucket.exports) == 2
    error_message = "Expected one export bucket per quarter."
  }

  assert {
    condition     = google_storage_bucket.exports["2026-q1"].name == "meridian-test-export-2026-q1"
    error_message = "Export buckets are named <name_prefix>-export-<quarter>."
  }
}

run "no_exports_by_default" {
  command = plan

  assert {
    condition     = length(google_storage_bucket.exports) == 0
    error_message = "export_quarters should default to an empty list (prod has none)."
  }
}

run "uppercase_quarter_rejected" {
  command = plan

  variables {
    export_quarters = ["2026-Q1"]
  }

  expect_failures = [var.export_quarters]
}

run "quarter_five_rejected" {
  command = plan

  variables {
    export_quarters = ["2026-q5"]
  }

  expect_failures = [var.export_quarters]
}
