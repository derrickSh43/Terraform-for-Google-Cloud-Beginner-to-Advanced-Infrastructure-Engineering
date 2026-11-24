# Nightly sales reports - written by the reporting team in 2024 and pasted into the
# dev root "temporarily". Hard-coded project and names, no module, nothing in prod.
# Lesson 20: move these into modules/reporting WITHOUT destroying anything.

resource "google_service_account" "reporter" {
  project      = "meridian-dev-4821"
  account_id   = "sales-reports"
  display_name = "Nightly sales reports"
}

resource "google_storage_bucket" "reports" {
  project                     = "meridian-dev-4821"
  name                        = "meridian-dev-sales-reports"
  location                    = "US-CENTRAL1"
  uniform_bucket_level_access = true

  labels = {
    team = "reporting"
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket_iam_member" "reporter_writes" {
  bucket = google_storage_bucket.reports.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.reporter.email}"
}

resource "google_pubsub_topic" "report_ready" {
  project = "meridian-dev-4821"
  name    = "sales-report-ready"
}
