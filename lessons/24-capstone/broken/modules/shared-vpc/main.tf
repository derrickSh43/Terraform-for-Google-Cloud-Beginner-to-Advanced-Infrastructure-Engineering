# Shared VPC: the hub project owns the network; service projects run workloads
# in its subnets. Teams get networkUser on specific subnets, never the whole network.

resource "google_compute_shared_vpc_host_project" "this" {
  project = var.host_project_id
}

resource "google_compute_shared_vpc_service_project" "this" {
  for_each = var.service_projects

  host_project    = google_compute_shared_vpc_host_project.this.project
  service_project = each.key
}

resource "google_compute_subnetwork_iam_member" "users" {
  for_each = var.service_projects

  project    = var.host_project_id
  region     = var.region
  subnetwork = each.value.subnet_name
  role       = "roles/compute.networkUser"
  member     = each.value.member
}
