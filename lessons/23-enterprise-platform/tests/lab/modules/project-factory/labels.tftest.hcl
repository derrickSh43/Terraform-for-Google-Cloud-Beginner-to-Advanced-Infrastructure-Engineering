# Runs inside modules/project-factory.
mock_provider "google" {}
mock_provider "random" {}

variables {
  billing_account = "01A2B3-C4D5E6-F7A8B9"
  folders         = { dev = "folders/1", prod = "folders/2", shared = "folders/3" }
  shared_vpc_host = "meridian-net"
  projects = {
    "meridian-net" = { folder = "shared", env = "shared", cost_center = "cc-9000", owner = "team-platform", budget = 100 }
    "meridian-app" = { folder = "dev", env = "dev", cost_center = "cc-1001", owner = "team-shop", budget = 200, shared_vpc = true }
  }
}

run "labels_and_budgets" {
  command = plan

  assert {
    condition     = google_project.this["meridian-app"].labels["cost-center"] == "cc-1001" && google_project.this["meridian-app"].labels["env"] == "dev"
    error_message = "Projects must carry the cost-center and env labels from their settings."
  }

  assert {
    condition     = length(google_billing_budget.this) == 2
    error_message = "Every project needs a budget."
  }

  assert {
    condition     = google_project.this["meridian-app"].folder_id == "folders/1"
    error_message = "A project goes into the folder its settings name."
  }

  assert {
    condition     = length(google_compute_shared_vpc_service_project.this) == 1
    error_message = "Only projects with shared_vpc = true are attached."
  }
}

run "bad_cost_center_rejected" {
  command = plan

  variables {
    projects = {
      "meridian-net" = { folder = "shared", env = "shared", cost_center = "marketing", owner = "team-platform", budget = 100 }
    }
  }

  expect_failures = [var.projects]
}

run "unknown_env_rejected" {
  command = plan

  variables {
    projects = {
      "meridian-net" = { folder = "shared", env = "staging", cost_center = "cc-9000", owner = "team-platform", budget = 100 }
    }
  }

  expect_failures = [var.projects]
}

run "missing_owner_rejected" {
  command = plan

  variables {
    projects = {
      "meridian-net" = { folder = "shared", env = "shared", cost_center = "cc-9000", owner = " ", budget = 100 }
    }
  }

  expect_failures = [var.projects]
}
