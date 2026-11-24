# Organisation-level resources aren't in a project, but API quota and billing
# for the calls are charged to the seed project.
provider "google" {
  project               = var.seed_project_id
  region                = var.region
  billing_project       = var.seed_project_id
  user_project_override = true
}
