# A regional internal passthrough load balancer:
#   forwarding rule (internal IP) -> regional backend service -> instance group
#                                              ^ regional health check
# The backend service only sends new connections to healthy VMs, in every zone.

resource "google_compute_region_health_check" "this" {
  name                = "${var.name}-hc"
  region              = var.region
  check_interval_sec  = 5
  timeout_sec         = 5
  healthy_threshold   = 2
  unhealthy_threshold = 2

  http_health_check {
    port         = var.port
    request_path = var.health_check_path
  }
}

resource "google_compute_region_backend_service" "this" {
  name                  = "${var.name}-backend"
  region                = var.region
  load_balancing_scheme = "INTERNAL"
  protocol              = "TCP"
  health_checks         = [google_compute_region_health_check.this.id]

  backend {
    group          = var.instance_group
    balancing_mode = "CONNECTION"
  }
}

resource "google_compute_forwarding_rule" "this" {
  name                  = "${var.name}-ilb"
  region                = var.region
  load_balancing_scheme = "INTERNAL"
  backend_service       = google_compute_region_backend_service.this.id
  ip_protocol           = "TCP"
  ports                 = [tostring(var.port)]
  network               = var.network_id
  subnetwork            = var.subnet_id
}
