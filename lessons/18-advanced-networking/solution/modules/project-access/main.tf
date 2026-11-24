# Human access, by group only. Joining or leaving a team is a group change in
# Workspace / Cloud Identity, not a Terraform change - and nobody gets a role
# as an individual.

locals {
  grants = {
    for pair in flatten([
      for principal, roles in var.group_roles : [
        for role in roles : { principal = principal, role = role }
      ]
    ]) : "${pair.principal} ${pair.role}" => pair
  }
}

resource "google_project_iam_member" "this" {
  for_each = local.grants

  project = var.project_id
  role    = each.value.role
  member  = each.value.principal
}
