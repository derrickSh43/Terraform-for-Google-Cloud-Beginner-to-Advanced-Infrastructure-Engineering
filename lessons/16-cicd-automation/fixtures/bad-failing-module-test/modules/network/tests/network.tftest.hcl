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
    condition     = google_compute_subnetwork.this["web"].name == "web"
    error_message = "Subnet names must be <name_prefix>-<tier>."
  }

  assert {
    condition     = alltrue([for s in google_compute_subnetwork.this : s.private_ip_google_access])
    error_message = "Every subnet needs Private Google Access."
  }
}

run "vpc_is_custom_mode" {
  command = plan

  assert {
    condition     = google_compute_network.this.auto_create_subnetworks == false
    error_message = "The VPC must be custom mode."
  }
}

run "nat_is_off_by_default" {
  command = plan

  assert {
    condition     = length(google_compute_router_nat.this) == 0 && length(google_compute_router.this) == 0
    error_message = "No router or NAT unless enable_nat = true."
  }
}

run "nat_when_enabled" {
  command = plan

  variables {
    enable_nat = true
  }

  assert {
    condition     = length(google_compute_router_nat.this) == 1
    error_message = "enable_nat = true should create one Cloud NAT."
  }

  assert {
    condition     = google_compute_router_nat.this[0].log_config[0].filter == "ERRORS_ONLY"
    error_message = "NAT should log errors."
  }
}

run "secondary_ranges_land_on_the_right_subnet" {
  command = plan

  variables {
    secondary_ranges = {
      app = { pods = "10.8.0.0/17" }
    }
  }

  assert {
    condition     = length(google_compute_subnetwork.this["app"].secondary_ip_range) == 1
    error_message = "The app subnet should get one secondary range."
  }

  assert {
    condition     = length(google_compute_subnetwork.this["web"].secondary_ip_range) == 0
    error_message = "Other subnets must not get secondary ranges."
  }
}
