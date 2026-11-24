# A self-healing, autoscaling workload:
#   identity (SA + roles) -> instance template -> regional MIG -> autoscaler
#
# The service account and IAM resources keep the same addresses as in
# vm-service, so switching module "web" to this module leaves them untouched.

resource "google_service_account" "this" {
  account_id   = "meridian-${var.name}"
  display_name = var.display_name
  description  = var.description
}

resource "google_project_iam_member" "this" {
  for_each = var.roles

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.this.email}"
}

# Templates are immutable: every change creates a new one. name_prefix plus
# create_before_destroy lets the MIG roll to the new template before the old
# one is deleted.
resource "google_compute_instance_template" "this" {
  name_prefix  = "meridian-${var.name}-"
  machine_type = var.machine_type

  tags   = [var.name]
  labels = merge(var.labels, { role = var.name })

  disk {
    source_image = "debian-cloud/debian-12"
    boot         = true
    auto_delete  = true
    disk_size_gb = 10
    disk_type    = "pd-balanced"
  }

  network_interface {
    subnetwork = var.subnet_id
    # no access_config: traffic arrives via the load balancer, egress via Cloud NAT
  }

  metadata = {
    enable-oslogin = "TRUE"
  }

  metadata_startup_script = var.startup_script

  service_account {
    email  = google_service_account.this.email
    scopes = ["cloud-platform"]
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Autohealing gets its own, more tolerant check: the load balancer should stop
# sending traffic quickly, but recreating a VM is expensive.
resource "google_compute_health_check" "autoheal" {
  name                = "meridian-${var.name}-autoheal"
  check_interval_sec  = 15
  timeout_sec         = 5
  healthy_threshold   = 2
  unhealthy_threshold = 4

  http_health_check {
    port         = var.port
    request_path = var.health_check_path
  }
}

resource "google_compute_region_instance_group_manager" "this" {
  name                      = "meridian-${var.name}-mig"
  region                    = var.region
  base_instance_name        = "meridian-${var.name}"
  distribution_policy_zones = var.zones
  # EVEN: the MIG keeps the same number of VMs in every zone, so losing a zone
  # costs at most ceil(n / zones) VMs. (BALANCED/ANY may pile VMs into one zone.)
  distribution_policy_target_shape = "EVEN"

  version {
    instance_template = google_compute_instance_template.this.id
  }

  named_port {
    name = "http"
    port = var.port
  }

  auto_healing_policies {
    health_check      = google_compute_health_check.autoheal.id
    initial_delay_sec = var.autoheal_initial_delay_sec
  }

  # Roll out new templates by adding VMs first, never dropping below capacity.
  update_policy {
    type                  = "PROACTIVE"
    minimal_action        = "REPLACE"
    replacement_method    = "SUBSTITUTE"
    max_surge_fixed       = length(var.zones) # regional MIGs need 0 or >= number of zones
    max_unavailable_fixed = 0
  }

  depends_on = [google_project_iam_member.this]
}

resource "google_compute_region_autoscaler" "this" {
  name   = "meridian-${var.name}-autoscaler"
  region = var.region
  target = google_compute_region_instance_group_manager.this.id

  autoscaling_policy {
    min_replicas    = var.min_replicas
    max_replicas    = var.max_replicas
    cooldown_period = 90 # boot + startup script before metrics count

    cpu_utilization {
      target = var.cpu_target
    }
  }
}

# Buckets the workload may write objects to (same address as in vm-service, so
# switching a module from vm-service keeps the grants).
resource "google_storage_bucket_iam_member" "writer" {
  for_each = toset(var.writable_buckets)

  bucket = each.value
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.this.email}"
}
