# Tests for modules/landing-zone (capstone). No credentials: mock provider.
mock_provider "google" {}

variables {
  org_id          = "123456789012"
  platform_group  = "platform@meridian.example"
  developer_group = "developers@meridian.example"
}

run "folder_hierarchy" {
  command = plan

  assert {
    condition     = google_folder.meridian.parent == "organizations/123456789012"
    error_message = "The Meridian folder must sit directly under the organization."
  }

  assert {
    condition     = toset(keys(google_folder.env)) == toset(["dev", "prod", "shared"])
    error_message = "Expected dev, prod and shared folders under Meridian."
  }

  assert {
    condition     = google_folder.meridian.deletion_protection && alltrue([for f in google_folder.env : f.deletion_protection])
    error_message = "Every folder must be protected from deletion."
  }
}

run "guardrails_and_access" {
  command = plan

  assert {
    condition     = contains(keys(google_org_policy_policy.enforced), "iam.disableServiceAccountKeyCreation")
    error_message = "Service account key creation must be blocked on the Meridian folder."
  }

  assert {
    condition     = google_folder_iam_member.platform_admin.member == "group:platform@meridian.example"
    error_message = "The platform team administers the Meridian folder as a group."
  }

  assert {
    condition     = alltrue([for m in google_folder_iam_member.developers : m.member == "group:developers@meridian.example"])
    error_message = "Developer roles go to the developer group."
  }
}

run "custom_environments" {
  command = plan

  variables {
    environments = ["dev", "prod", "shared", "sandbox"]
  }

  assert {
    condition     = length(google_folder.env) == 4
    error_message = "One folder per entry in var.environments."
  }
}
