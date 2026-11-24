# A private, VPC-native GKE Autopilot cluster for batch workloads.

# Nodes run as their own minimal identity, not the default compute service account.
resource "google_service_account" "nodes" {
  account_id   = "${var.name}-nodes"
  display_name = "GKE nodes (${var.name})"
}

resource "google_project_iam_member" "nodes" {
  project = var.project_id
  role    = "roles/editor"
  member  = "serviceAccount:${google_service_account.nodes.email}"
}

resource "google_container_cluster" "this" {
  name     = var.name
  location = var.region # regional: control plane and nodes across zones

  enable_autopilot    = true
  deletion_protection = true

  network    = var.network_id
  subnetwork = var.subnet_id

  # VPC-native: pods and services get IPs from the subnet's secondary ranges.
  ip_allocation_policy {
    cluster_secondary_range_name  = var.pods_range_name
    services_secondary_range_name = var.services_range_name
  }

  private_cluster_config {
    enable_private_nodes    = true # nodes have no external IPs
    enable_private_endpoint = true # the control plane has no public endpoint
    master_ipv4_cidr_block  = var.master_cidr

    master_global_access_config {
      enabled = true
    }
  }

  # Who may talk to the Kubernetes API (kubectl, CI): private ranges only.
  master_authorized_networks_config {
    dynamic "cidr_blocks" {
      for_each = var.authorized_networks
      content {
        display_name = cidr_blocks.key
        cidr_block   = cidr_blocks.value
      }
    }
  }

  # Pods authenticate to Google APIs as Google service accounts - no node credentials, no keys.
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  release_channel {
    channel = var.release_channel
  }

  # Upgrades only at weekends (UTC).
  maintenance_policy {
    recurring_window {
      start_time = "2026-01-03T04:00:00Z"
      end_time   = "2026-01-03T10:00:00Z"
      recurrence = "FREQ=WEEKLY;BYDAY=SA,SU"
    }
  }

  cluster_autoscaling {
    auto_provisioning_defaults {
      service_account = google_service_account.nodes.email
      oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    }
  }

  resource_labels = var.labels

  depends_on = [google_project_iam_member.nodes]
}

# --- A workload identity for the report-generator batch job ------------------
resource "google_service_account" "workload" {
  for_each = var.workloads

  account_id   = "meridian-${each.key}"
  display_name = "GKE workload ${each.key}"
}

# Exactly one Kubernetes service account may act as each Google service account.
resource "google_service_account_iam_member" "workload_identity" {
  for_each = var.workloads

  service_account_id = google_service_account.workload[each.key].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${each.value}]"
}
