mock_provider "google" {}

run "default_subnets_plan" {
  command = plan
}

run "invalid_cidr_is_rejected" {
  command = plan

  variables {
    subnets = {
      web = "10.10.1.0/24"
      app = "10.10.2.0/33"
    }
  }

  expect_failures = [var.subnets]
}

run "web_tier_is_mandatory" {
  command = plan

  variables {
    subnets = {
      app = "10.10.2.0/24"
    }
  }

  expect_failures = [var.subnets]
}
