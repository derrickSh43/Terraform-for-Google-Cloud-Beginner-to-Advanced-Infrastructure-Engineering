# The CI pipeline's identity, done properly:
#   * a custom role with exactly the permissions CI uses - not roles/editor
#   * object access on the assets bucket only - bucket-level, not project-level IAM
#   * no keys: named groups may impersonate the account (short-lived tokens)

resource "google_service_account" "this" {
  account_id   = var.account_id
  display_name = var.display_name
}

resource "google_project_iam_custom_role" "deployer" {
  role_id     = var.role_id
  title       = "Meridian CI deployer"
  description = "Roll the web MIG to a new template and read what it needs. Nothing else."
  permissions = var.permissions
  stage       = "GA"
}

resource "google_project_iam_member" "deployer" {
  project = var.project_id
  role    = google_project_iam_custom_role.deployer.id
  member  = "serviceAccount:${google_service_account.this.email}"
}

# Resource-level IAM: the grant lives on the bucket, so it reaches nothing else.
resource "google_storage_bucket_iam_member" "assets" {
  bucket = var.assets_bucket
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.this.email}"
}

# Impersonation instead of keys: these principals can mint short-lived tokens
# for the CI account (gcloud --impersonate-service-account / provider
# impersonate_service_account). Granted on the account, not the project.
resource "google_project_iam_member" "impersonators" {
  for_each = toset(var.impersonators)

  project = var.project_id
  role    = "roles/iam.serviceAccountTokenCreator" # "simpler than per-account grants"
  member  = each.value
}
