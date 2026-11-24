resource "google_project_iam_member" "oncall" {
  project = var.project_id
  role    = "roles/compute.viewer"
  member  = "user:alex@meridianbooks.example"
}
