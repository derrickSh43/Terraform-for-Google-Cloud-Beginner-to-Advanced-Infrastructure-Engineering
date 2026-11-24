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

  # Human access expires and must be renewed deliberately.
  dynamic "condition" {
    for_each = var.expires == "" ? [] : [var.expires]
    content {
      title       = "expires-${substr(condition.value, 0, 10)}"
      description = "Temporary access - renew by changing var.expires."
      expression  = "request.time < timestamp(\"${condition.value}\")"
    }
  }
}
