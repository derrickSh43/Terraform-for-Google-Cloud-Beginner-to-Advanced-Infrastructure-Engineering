# Tests the data-disk option of modules/vm-service on its own.
mock_provider "google" {}

variables {
  name           = "app"
  display_name   = "Test"
  description    = "Module test"
  project_id     = "test-project"
  zone           = "us-central1-a"
  subnet_id      = "projects/test-project/regions/us-central1/subnetworks/app"
  startup_script = "#!/bin/sh"
  labels         = { app = "meridian", env = "test", managed_by = "terraform" }
}

run "no_disk_by_default" {
  command = plan

  module {
    source = "../../modules/vm-service"
  }

  assert {
    condition     = length(google_compute_disk.data) == 0 && length(google_compute_resource_policy.snapshots) == 0
    error_message = "With data_disk_size_gb = 0 there must be no disk and no snapshot policy."
  }
}

run "disk_brings_snapshots" {
  command = plan

  module {
    source = "../../modules/vm-service"
  }

  variables {
    data_disk_size_gb = 20
  }

  assert {
    condition     = google_compute_disk.data[0].size == 20
    error_message = "The data disk should use data_disk_size_gb."
  }

  assert {
    condition     = google_compute_resource_policy.snapshots[0].region == "us-central1"
    error_message = "The snapshot policy must be in the disk's region."
  }
}

run "tiny_disk_is_rejected" {
  command = plan

  module {
    source = "../../modules/vm-service"
  }

  variables {
    data_disk_size_gb = 5
  }

  expect_failures = [var.data_disk_size_gb]
}
