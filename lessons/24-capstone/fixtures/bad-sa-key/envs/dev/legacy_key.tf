# "Just for the migration script" - a key nobody will remember to delete.
resource "google_service_account_key" "migration" {
  service_account_id = "projects/meridian-dev/serviceAccounts/meridian-ci@meridian-dev.iam.gserviceaccount.com"
}
