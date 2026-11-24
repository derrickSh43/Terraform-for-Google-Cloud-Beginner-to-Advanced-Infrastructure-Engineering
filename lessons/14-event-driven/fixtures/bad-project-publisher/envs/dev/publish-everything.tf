resource "google_project_iam_member" "app_publishes" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${module.app.service_account_email}"
}
