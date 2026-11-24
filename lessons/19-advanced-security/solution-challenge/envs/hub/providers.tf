# Two configurations of the same provider: the hub project (default) and a second
# project that simulates the on-prem data centre. Resources and modules choose
# with `provider = google.onprem` / `providers = { google = google.onprem }`.
provider "google" {
  project = var.hub_project_id
  region  = var.region
}

provider "google" {
  alias   = "onprem"
  project = var.onprem_project_id
  region  = var.region
}
