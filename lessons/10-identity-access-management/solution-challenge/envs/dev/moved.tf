# The CI service account already exists in dev (legacy-access.tf). Keep it -
# its identity is referenced by the CI system - and move it into the module.
moved {
  from = google_service_account.ci
  to   = module.ci.google_service_account.this
}
