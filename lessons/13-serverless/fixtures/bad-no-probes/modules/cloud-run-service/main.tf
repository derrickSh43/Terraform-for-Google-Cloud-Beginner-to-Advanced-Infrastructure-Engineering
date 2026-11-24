# A Cloud Run service reachable only through the external load balancer,
# with its own identity, private egress into the VPC, and secrets from Secret Manager.

resource "google_service_account" "this" {
  account_id   = "meridian-${var.name}"
  display_name = "Meridian ${var.name} (Cloud Run)"
}

resource "google_cloud_run_v2_service" "this" {
  name     = "meridian-${var.name}"
  location = var.region

  # Only the load balancer can reach it - not the *.run.app URL from the internet.
  ingress = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  # Requests arrive through the load balancer, so Cloud Run's per-request IAM check
  # is replaced by ingress control. No allUsers invoker binding is needed.
  invoker_iam_disabled = true

  deletion_protection = var.deletion_protection
  labels              = var.labels

  # Canary: a fixed share of traffic stays on the known-good revision.
  dynamic "traffic" {
    for_each = var.stable_revision == "" ? [] : [1]
    content {
      type     = "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION"
      revision = var.stable_revision
      percent  = 100 - var.canary_percent
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = var.stable_revision == "" ? 100 : var.canary_percent
  }

  template {
    service_account                  = google_service_account.this.email
    max_instance_request_concurrency = 80

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    containers {
      image = var.image # pinned by digest: the same bytes every deploy

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle          = true # only billed for CPU while handling requests
        startup_cpu_boost = true
      }


      dynamic "env" {
        for_each = var.env
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = var.secret_env
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }
    }

    # Direct VPC egress: private IPs (Cloud SQL) go through the VPC; the internet doesn't.
    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"
      network_interfaces {
        network    = var.network_id
        subnetwork = var.subnet_id
        tags       = [var.name]
      }
    }
  }
}

# Lets the load balancer send traffic to the service.
resource "google_compute_region_network_endpoint_group" "this" {
  name                  = "meridian-${var.name}-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.this.name
  }
}
