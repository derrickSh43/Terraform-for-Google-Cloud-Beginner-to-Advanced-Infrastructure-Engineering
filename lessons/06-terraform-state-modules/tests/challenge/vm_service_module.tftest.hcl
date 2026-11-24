# Tests the reusable VM module on its own, outside any environment.
# A run block can point `module.source` at any local module.
mock_provider "google" {}

variables {
  name           = "web"
  display_name   = "Test web tier"
  description    = "Module test"
  project_id     = "test-project"
  zone           = "us-central1-a"
  subnet_id      = "projects/test-project/regions/us-central1/subnetworks/test"
  startup_script = "#!/bin/sh"
  labels         = { app = "meridian", env = "test", managed_by = "terraform" }
}

run "defaults_build_a_private_micro_vm" {
  command = plan

  module {
    source = "../../modules/vm-service"
  }

  assert {
    condition     = google_compute_instance.this.machine_type == "e2-micro"
    error_message = "Default machine type should be e2-micro."
  }

  assert {
    condition     = length(google_compute_instance.this.network_interface[0].access_config) == 0
    error_message = "external_ip defaults to false, so there must be no access_config."
  }

  assert {
    condition     = google_compute_instance.this.labels["role"] == "web"
    error_message = "The module should add a role label from var.name."
  }
}

run "external_ip_adds_access_config" {
  command = plan

  module {
    source = "../../modules/vm-service"
  }

  variables {
    external_ip = true
  }

  assert {
    condition     = length(google_compute_instance.this.network_interface[0].access_config) == 1
    error_message = "external_ip = true should add exactly one access_config."
  }
}

run "large_machine_types_are_rejected" {
  command = plan

  module {
    source = "../../modules/vm-service"
  }

  variables {
    machine_type = "n2-standard-16"
  }

  expect_failures = [var.machine_type]
}
