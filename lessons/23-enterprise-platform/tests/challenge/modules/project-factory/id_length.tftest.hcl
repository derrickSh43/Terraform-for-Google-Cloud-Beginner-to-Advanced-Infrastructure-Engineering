# Runs inside modules/project-factory.
mock_provider "google" {}
mock_provider "random" {}

variables {
  billing_account = "01A2B3-C4D5E6-F7A8B9"
  folders         = { dev = "folders/1", prod = "folders/2", shared = "folders/3" }
  shared_vpc_host = "meridian-network"
}

run "twenty_five_characters_allowed" {
  command = plan

  variables {
    projects = {
      "meridian-network"         = { folder = "shared", env = "shared", cost_center = "cc-9000", owner = "team-platform", budget = 100 }
      "meridian-catalog-search1" = { folder = "dev", env = "dev", cost_center = "cc-1001", owner = "team-shop", budget = 100 }
    }
  }

  assert {
    condition     = length(google_project.this) == 2
    error_message = "Names up to 25 characters are valid."
  }
}

run "long_name_rejected" {
  command = plan

  variables {
    projects = {
      "meridian-network"             = { folder = "shared", env = "shared", cost_center = "cc-9000", owner = "team-platform", budget = 100 }
      "meridian-recommendations-dev" = { folder = "dev", env = "dev", cost_center = "cc-1001", owner = "team-shop", budget = 100 }
    }
  }

  expect_failures = [var.projects]
}
