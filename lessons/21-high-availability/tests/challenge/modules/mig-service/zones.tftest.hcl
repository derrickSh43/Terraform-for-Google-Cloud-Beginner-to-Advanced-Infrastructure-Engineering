# Runs inside modules/mig-service.
mock_provider "google" {}

variables {
  name           = "test"
  display_name   = "Test"
  description    = "Test workload"
  project_id     = "test-project"
  region         = "us-central1"
  zones          = ["us-central1-a", "us-central1-b", "us-central1-c"]
  subnet_id      = "projects/test-project/regions/us-central1/subnetworks/test"
  startup_script = "#!/bin/bash"
  labels         = { app = "meridian" }
  min_replicas   = 3
  max_replicas   = 6
}

run "three_zones_spread_evenly" {
  command = plan

  assert {
    condition     = google_compute_region_instance_group_manager.this.distribution_policy_target_shape == "EVEN"
    error_message = "VMs must be spread evenly across zones."
  }

  assert {
    condition     = length(google_compute_region_instance_group_manager.this.distribution_policy_zones) == 3
    error_message = "The MIG must use every zone it's given."
  }
}

run "single_zone_rejected" {
  command = plan

  variables {
    zones        = ["us-central1-a"]
    min_replicas = 2
  }

  expect_failures = [var.zones]
}

run "fewer_vms_than_zones_rejected" {
  command = plan

  variables {
    min_replicas = 2
  }

  expect_failures = [var.min_replicas]
}
