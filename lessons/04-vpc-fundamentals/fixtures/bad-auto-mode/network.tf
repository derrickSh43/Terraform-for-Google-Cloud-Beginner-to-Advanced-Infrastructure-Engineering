# Custom-mode VPC: no surprise subnets in every region, we choose every range.
resource "google_compute_network" "main" {
  name                    = "meridian-${var.environment}-vpc"
  auto_create_subnetworks = true
  routing_mode            = "REGIONAL"

  depends_on = [google_project_service.apis]
}

resource "google_compute_subnetwork" "web" {
  name          = "meridian-${var.environment}-web"
  region        = var.region
  network       = google_compute_network.main.id
  ip_cidr_range = var.web_subnet_cidr

  # Lets VMs without external IPs reach Google APIs (Cloud Storage, Logging...).
  private_ip_google_access = true
}
