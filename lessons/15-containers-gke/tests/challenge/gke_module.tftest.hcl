# Tests modules/gke-autopilot on its own.
mock_provider "google" {}

variables {
  name        = "test-batch"
  project_id  = "test-project"
  region      = "us-central1"
  network_id  = "projects/test-project/global/networks/vpc"
  subnet_id   = "projects/test-project/regions/us-central1/subnetworks/gke"
  master_cidr = "172.16.0.0/28"
  labels      = { app = "meridian", env = "test", managed_by = "terraform" }

  authorized_networks = { ops = "10.110.0.0/24" }
}

run "private_ranges_are_accepted" {
  command = plan

  module {
    source = "../../modules/gke-autopilot"
  }

  assert {
    condition     = google_container_cluster.this.private_cluster_config[0].enable_private_endpoint
    error_message = "The control plane must stay private."
  }
}

run "anywhere_is_rejected" {
  command = plan

  module {
    source = "../../modules/gke-autopilot"
  }

  variables {
    authorized_networks = { laptop = "0.0.0.0/0" }
  }

  expect_failures = [var.authorized_networks]
}

run "public_range_is_rejected" {
  command = plan

  module {
    source = "../../modules/gke-autopilot"
  }

  variables {
    authorized_networks = { office = "203.0.113.0/24" }
  }

  expect_failures = [var.authorized_networks]
}
