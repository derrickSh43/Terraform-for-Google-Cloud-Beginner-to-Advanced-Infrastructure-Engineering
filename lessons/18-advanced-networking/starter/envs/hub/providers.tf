provider "google" {
  project = var.hub_project_id
  region  = var.region
}

# TODO (R18.1): a second, aliased provider "google" for var.onprem_project_id.
