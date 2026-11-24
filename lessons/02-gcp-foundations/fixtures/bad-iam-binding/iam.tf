# One identity per workload. The web VMs (lesson 3) will run as this account
# instead of the over-privileged Compute Engine default service account.
resource "google_service_account" "web" {
  account_id   = "meridian-web"
  display_name = "Meridian web tier"
  description  = "Runs the Meridian storefront VMs."

  depends_on = [google_project_service.apis]
}

locals {
  web_roles = toset([
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
  ])
}

# _member is additive: it grants one role to one principal and leaves every
# other grant in the project alone. (_binding and _policy are authoritative.)
resource "google_project_iam_member" "web" {
  for_each = local.web_roles

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.web.email}"
}

# A teammate "simplified" log access - this REPLACES every logWriter grant in the project.
resource "google_project_iam_binding" "logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  members = ["serviceAccount:${google_service_account.web.email}"]
}
