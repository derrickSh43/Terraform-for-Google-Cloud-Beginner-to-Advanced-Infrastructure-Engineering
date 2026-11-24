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

# The archive bucket was created by hand in the console. Adopt it instead of
# creating a new one (the name is taken, so a create would fail anyway).
import {
  to = module.reporting.google_storage_bucket.archive
  id = "meridian-dev-report-archive"
}

# The auditors' quarterly export buckets, also created by hand: one import block
# for all of them.
import {
  for_each = toset(["2025-q3", "2025-q4"])
  to       = module.reporting.google_storage_bucket.exports[each.key]
  id       = "meridian-dev-export-${each.key}"
}
