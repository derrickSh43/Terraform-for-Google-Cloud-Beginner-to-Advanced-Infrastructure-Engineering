# The organisation's skeleton: one Meridian folder, one folder per environment
# under it, guardrails and access set ONCE at folder level and inherited by
# every project below.
#
#   organizations/<org>
#   └── Meridian                  <- guardrails, platform team, central log sink
#       ├── dev                   <- developers may work here
#       ├── prod
#       └── shared                <- network host, logging

resource "google_folder" "meridian" {
  display_name        = "Meridian"
  parent              = "organizations/${var.org_id}"
  deletion_protection = true
}

resource "google_folder" "env" {
  for_each = toset(var.environments)

  display_name        = each.value
  parent              = google_folder.meridian.name
  deletion_protection = true
}

# Guardrails on the top folder apply to every project underneath, existing or future.
resource "google_org_policy_policy" "enforced" {
  for_each = toset(var.boolean_constraints)

  name   = "${google_folder.meridian.name}/policies/${each.value}"
  parent = google_folder.meridian.name

  spec {
    rules {
      enforce = "TRUE"
    }
  }
}

# Access follows the hierarchy too: grant on the folder, not on each project.
resource "google_folder_iam_member" "platform_admin" {
  folder = google_folder.meridian.name
  role   = "roles/resourcemanager.folderAdmin"
  member = "group:${var.platform_group}"
}

resource "google_folder_iam_member" "developers" {
  for_each = toset(var.developer_roles)

  folder = google_folder.env["dev"].name
  role   = each.value
  member = "group:${var.developer_group}"
}
