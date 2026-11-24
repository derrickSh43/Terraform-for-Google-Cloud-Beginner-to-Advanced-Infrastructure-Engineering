# Nightly sales reports: the reporting team's resources, formerly a flat file in
# the dev root. Everything that differs between environments is a variable.

resource "google_service_account" "reporter" {
  project      = var.project_id
  account_id   = "sales-reports"
  display_name = "Nightly sales reports"
}

resource "google_storage_bucket" "reports" {
  project                     = var.project_id
  name                        = "${var.name_prefix}-sales-reports"
  location                    = upper(var.region)
  uniform_bucket_level_access = true
  labels                      = var.labels

  lifecycle_rule {
    condition {
      age = var.retention_days
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

# Created by hand in the console in 2025. Adopted with an import block in the
# root; the configuration describes the bucket exactly as it exists.
resource "google_storage_bucket" "archive" {
  project                     = var.project_id
  name                        = "${var.name_prefix}-report-archive"
  location                    = upper(var.region)
  storage_class               = "NEARLINE"
  uniform_bucket_level_access = true
  labels                      = var.labels

  lifecycle_rule {
    condition {
      age = 730
    }
    action {
      type = "Delete"
    }
  }
}

# One bucket per quarterly export for the auditors (created by hand, adopted
# with a for_each import block in the root).
resource "google_storage_bucket" "exports" {
  for_each = toset(var.export_quarters)

  project                     = var.project_id
  name                        = "${var.name_prefix}-export-${each.key}"
  location                    = upper(var.region)
  storage_class               = "COLDLINE"
  uniform_bucket_level_access = true
  labels                      = var.labels

  lifecycle {
    prevent_destroy = true
  }
}

# Post-conditions on the deployed reality, re-evaluated on every plan. A failed
# check is a warning, not an error: it tells you something drifted.
check "reports_stay_private_and_short_lived" {
  assert {
    condition     = google_storage_bucket.reports.uniform_bucket_level_access
    error_message = "The reports bucket must use uniform bucket-level access (no per-object ACLs)."
  }

  assert {
    condition     = alltrue([for r in google_storage_bucket.reports.lifecycle_rule : one(r.condition).age <= 365])
    error_message = "Daily reports must be deleted within 365 days."
  }

  assert {
    condition     = google_storage_bucket.archive.storage_class != "STANDARD"
    error_message = "The archive belongs in a cold storage class."
  }
}
