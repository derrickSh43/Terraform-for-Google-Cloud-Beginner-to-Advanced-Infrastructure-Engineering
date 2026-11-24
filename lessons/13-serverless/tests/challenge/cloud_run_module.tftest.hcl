# Tests modules/cloud-run-service on its own.
mock_provider "google" {}

variables {
  name       = "catalog"
  region     = "us-central1"
  network_id = "projects/p/global/networks/vpc"
  subnet_id  = "projects/p/regions/us-central1/subnetworks/serverless"
  labels     = { app = "meridian", env = "test", managed_by = "terraform" }
  image      = "us-central1-docker.pkg.dev/p/meridian/catalog@sha256:4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f"
}

run "digest_pinned_image_is_accepted" {
  command = plan

  module {
    source = "../../modules/cloud-run-service"
  }

  assert {
    condition     = google_cloud_run_v2_service.this.ingress == "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
    error_message = "The service must only accept traffic from the load balancer."
  }
}

run "latest_tag_is_rejected" {
  command = plan

  module {
    source = "../../modules/cloud-run-service"
  }

  variables {
    image = "us-central1-docker.pkg.dev/p/meridian/catalog:latest"
  }

  expect_failures = [var.image]
}

run "docker_hub_is_rejected" {
  command = plan

  module {
    source = "../../modules/cloud-run-service"
  }

  variables {
    image = "docker.io/library/nginx@sha256:4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f"
  }

  expect_failures = [var.image]
}
