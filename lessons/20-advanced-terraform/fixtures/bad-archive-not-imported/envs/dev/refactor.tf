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

moved {
  from = google_pubsub_topic.report_ready
  to   = module.reporting.google_pubsub_topic.report_ready
}

# The archive bucket was created by hand in the console. Adopt it instead of
# creating a new one (the name is taken, so a create would fail anyway).
