resource "google_project_iam_binding" "log_writers" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  members = ["serviceAccount:meridian-web@meridian-dev-4821.iam.gserviceaccount.com"]
}
