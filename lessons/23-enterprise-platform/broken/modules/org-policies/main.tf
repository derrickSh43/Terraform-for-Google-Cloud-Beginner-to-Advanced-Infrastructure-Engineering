# Preventive guardrails: the API refuses these configurations for everyone in
# the project, including Owners and Terraform itself.

resource "google_project_service" "orgpolicy" {
  service            = "orgpolicy.googleapis.com"
  disable_on_destroy = false
}

resource "google_org_policy_policy" "enforced" {
  for_each = toset(var.boolean_constraints)

  name   = "projects/${var.project_id}/policies/${each.value}"
  parent = "projects/${var.project_id}"

  spec {
    rules {
      enforce = "TRUE"
    }
  }

  depends_on = [google_project_service.orgpolicy]
}

# No VM in the project may have an external IP (list constraint, deny all).
resource "google_org_policy_policy" "no_external_ips" {
  name   = "projects/${var.project_id}/policies/compute.vmExternalIpAccess"
  parent = "projects/${var.project_id}"

  spec {
    rules {
      deny_all = "TRUE"
    }
  }

  depends_on = [google_project_service.orgpolicy]
}
