# Refactoring the legacy reporting file: each resource keeps its deployed object,
# only its address changes. Keep these blocks until every state that had the old
# addresses has been applied (here: dev only - prod never had them).

moved {
  from = google_service_account.reporter
  to   = module.reporting.google_service_account.reporter
}

moved {
  from = google_storage_bucket.reports
  to   = module.reporting.google_storage_bucket.reports
}

moved {
  from = google_storage_bucket_iam_member.reporter_writes
  to   = module.reporting.google_storage_bucket_iam_member.reporter_writes
}

# The events team now owns the report-ready topic in their own configuration.
# Stop managing it here without deleting it.
removed {
  from = google_pubsub_topic.report_ready

  lifecycle {
    destroy = false
  }
}

# The archive bucket was created by hand in the console. Adopt it instead of
# creating a new one (the name is taken, so a create would fail anyway).
import {
  to = module.reporting.google_storage_bucket.archive
  id = "meridian-dev-report-archive"
}

import {
  to = module.reporting.google_storage_bucket.exports["2025-q3"]
  id = "meridian-dev-export-2025-q3"
}

import {
  to = module.reporting.google_storage_bucket.exports["2025-q4"]
  id = "meridian-dev-export-2025-q4"
}
