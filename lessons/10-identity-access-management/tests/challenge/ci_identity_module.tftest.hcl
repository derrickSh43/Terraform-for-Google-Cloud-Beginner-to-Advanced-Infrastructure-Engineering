# Tests modules/ci-identity on its own.
mock_provider "google" {}

variables {
  project_id    = "test-project"
  assets_bucket = "test-project-assets"
  impersonators = ["group:platform@example.com"]
}

run "defaults_are_least_privilege" {
  command = plan

  module {
    source = "../../modules/ci-identity"
  }

  assert {
    condition     = length(google_project_iam_custom_role.deployer.permissions) <= 15
    error_message = "The default CI role should stay small."
  }

  assert {
    condition     = length(google_iam_workload_identity_pool.github) == 0
    error_message = "Workload Identity Federation is off unless a repository is given."
  }
}

run "wildcards_are_rejected" {
  command = plan

  module {
    source = "../../modules/ci-identity"
  }

  variables {
    permissions = ["compute.*"]
  }

  expect_failures = [var.permissions]
}

run "set_iam_policy_is_rejected" {
  command = plan

  module {
    source = "../../modules/ci-identity"
  }

  variables {
    permissions = ["compute.instanceGroupManagers.get", "resourcemanager.projects.setIamPolicy"]
  }

  expect_failures = [var.permissions]
}
