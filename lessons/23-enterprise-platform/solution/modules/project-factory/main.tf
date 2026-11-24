# Every project is made the same way: in the right folder, with the mandatory
# labels, no default network, protected from deletion, with its APIs, a budget
# and (if it runs workloads) attached to the Shared VPC.

locals {
  labels = { for k, p in var.projects : k => {
    app           = "meridian"
    env           = p.env
    "cost-center" = p.cost_center
    owner         = p.owner
    managed_by    = "terraform"
  } }

  apis = merge([for k, p in var.projects : { for api in p.apis : "${k}/${api}" => { project = k, api = api } }]...)
}

resource "random_id" "suffix" {
  for_each = var.projects

  byte_length = 2
}

resource "google_project" "this" {
  for_each = var.projects

  name                = each.key
  project_id          = "${each.key}-${random_id.suffix[each.key].hex}"
  folder_id           = var.folders[each.value.folder]
  billing_account     = var.billing_account
  labels              = local.labels[each.key]
  auto_create_network = false     # the guardrail would block it anyway
  deletion_policy     = "PREVENT" # terraform destroy can't delete a project by accident
}

resource "google_project_service" "this" {
  for_each = local.apis

  project            = google_project.this[each.value.project].project_id
  service            = each.value.api
  disable_on_destroy = false
}

resource "google_billing_budget" "this" {
  for_each = var.projects

  billing_account = var.billing_account
  display_name    = "${each.key} monthly"

  budget_filter {
    projects = ["projects/${google_project.this[each.key].number}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(each.value.budget)
    }
  }

  threshold_rules {
    threshold_percent = 0.5
  }

  threshold_rules {
    threshold_percent = 0.9
  }

  threshold_rules {
    threshold_percent = 1.0
  }

  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "FORECASTED_SPEND"
  }
}

# Shared VPC: one host project owns the network; workload projects use its subnets.
resource "google_compute_shared_vpc_host_project" "host" {
  project = google_project.this[var.shared_vpc_host].project_id
}

resource "google_compute_shared_vpc_service_project" "this" {
  for_each = { for k, p in var.projects : k => p if p.shared_vpc }

  host_project    = google_compute_shared_vpc_host_project.host.project
  service_project = google_project.this[each.key].project_id
}
