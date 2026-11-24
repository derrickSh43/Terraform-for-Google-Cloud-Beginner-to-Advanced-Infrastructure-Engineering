# A Cloud Run service reachable only through the external load balancer,
# with its own identity, private egress into the VPC, and secrets from Secret Manager.

resource "google_service_account" "this" {
  account_id   = "meridian-${var.name}"
  display_name = "Meridian ${var.name} (Cloud Run)"
}

resource "google_cloud_run_v2_service" "this" {
  name     = "meridian-${var.name}"
  location = var.region

  # Default: only the load balancer can reach it. Workers use INGRESS_TRAFFIC_INTERNAL_ONLY.
  ingress = var.ingress

  # Behind a load balancer, ingress control replaces the per-request IAM check.
  # Services with named invokers (e.g. a Pub/Sub push identity) keep IAM on.
  invoker_iam_disabled = var.ingress == "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER" && length(var.invokers) == 0

  deletion_protection = var.deletion_protection
  labels              = var.labels

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
        cpu_idle = true # only billed for CPU while handling requests
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

# Lets the load balancer send traffic to the service (only for load-balanced services).
resource "google_compute_region_network_endpoint_group" "this" {
  for_each = var.create_neg ? toset(["main"]) : toset([])

  name                  = "meridian-${var.name}-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.this.name
  }
}

# Service-level IAM: exactly these identities may invoke the service.
resource "google_cloud_run_v2_service_iam_member" "invokers" {
  for_each = toset(var.invokers)

  name     = google_cloud_run_v2_service.this.name
  location = google_cloud_run_v2_service.this.location
  role     = "roles/run.invoker"
  member   = each.value
}
