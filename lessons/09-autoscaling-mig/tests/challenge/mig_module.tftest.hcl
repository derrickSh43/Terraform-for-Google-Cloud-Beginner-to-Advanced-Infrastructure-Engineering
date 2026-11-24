# Tests modules/mig-service on its own.
mock_provider "google" {}

variables {
  name           = "web"
  display_name   = "Test"
  description    = "Module test"
  project_id     = "test-project"
  region         = "us-central1"
  zones          = ["us-central1-a", "us-central1-b"]
  subnet_id      = "projects/test-project/regions/us-central1/subnetworks/web"
  startup_script = "#!/bin/sh"
  labels         = { app = "meridian", env = "test", managed_by = "terraform" }
}

run "defaults_are_highly_available" {
  command = plan

  module {
    source = "../../modules/mig-service"
  }

  assert {
    condition     = google_compute_region_autoscaler.this.autoscaling_policy[0].min_replicas >= 2
    error_message = "The default minimum must be at least 2 VMs."
  }

  assert {
    condition     = google_compute_region_instance_group_manager.this.update_policy[0].max_unavailable_fixed == 0
    error_message = "Rollouts must never take VMs out of service early."
  }
}

run "max_below_min_is_rejected" {
  command = plan

  module {
    source = "../../modules/mig-service"
  }

  variables {
    min_replicas = 4
    max_replicas = 2
  }

  expect_failures = [var.max_replicas]
}

run "runaway_max_is_rejected" {
  command = plan

  module {
    source = "../../modules/mig-service"
  }

  variables {
    max_replicas = 500
  }

  expect_failures = [var.max_replicas]
}
