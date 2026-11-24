# Enable APIs in whichever project the (possibly aliased) provider points at.
resource "google_project_service" "this" {
  for_each = var.apis

  service            = each.value
  disable_on_destroy = false
}
