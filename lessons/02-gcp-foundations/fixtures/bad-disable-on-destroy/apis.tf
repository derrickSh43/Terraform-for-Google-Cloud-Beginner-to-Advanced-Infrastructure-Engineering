locals {
  required_apis = toset([
    "compute.googleapis.com",
    "iam.googleapis.com",
    "storage.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
  ])
}

resource "google_project_service" "apis" {
  for_each = local.required_apis

  service = each.value

  # Never switch an API off just because this config is destroyed:
  # other teams' resources may depend on it.
  disable_on_destroy = true
}
