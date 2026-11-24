# Tests for modules/network, written as part of lesson 16.
# They run in CI on every pull request - no Google Cloud credentials needed.
mock_provider "google" {}

variables {
  name_prefix = "test"
  region      = "us-central1"
  subnets = {
    web = "10.0.1.0/24"
    app = "10.0.2.0/24"
  }
}

run "creates_one_subnet_per_tier" {
  command = plan

  assert {
    condition     = length(google_compute_subnetwork.this) == 2
    error_message = "Expected one subnet per entry in var.subnets."
  }

  assert {
    condition     = google_compute_subnetwork.this["web"].name == "test-web"
    error_message = "Subnet names must be <name_prefix>-<tier>."
  }

  assert {
    condition     = alltrue([for s in google_compute_subnetwork.this : s.private_ip_google_access])
    error_message = "Every subnet needs Private Google Access."
  }
}

