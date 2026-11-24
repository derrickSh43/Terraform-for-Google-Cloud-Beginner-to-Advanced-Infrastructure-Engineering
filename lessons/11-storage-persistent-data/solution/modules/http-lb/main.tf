# Global external Application Load Balancer, assembled from its parts:
#
#   address -> forwarding rule -> target proxy -> URL map -> backend service -> instance group(s) -> VMs
#                                                               ^ health check

resource "google_compute_global_address" "this" {
  name = "${var.name_prefix}-lb-ip"
}

resource "google_compute_health_check" "this" {
  name                = "${var.name_prefix}-http-hc"
  check_interval_sec  = 10
  timeout_sec         = 5
  healthy_threshold   = 2
  unhealthy_threshold = 3

  http_health_check {
    port         = var.port
    request_path = var.health_check_path
  }
}

resource "google_compute_backend_service" "this" {
  name                  = "${var.name_prefix}-web-backend"
  protocol              = "HTTP"
  port_name             = "http" # must match the instance group's named_port
  load_balancing_scheme = "EXTERNAL_MANAGED"
  timeout_sec           = 30
  health_checks         = [google_compute_health_check.this.id]

  # One backend per instance group (managed groups name their named_port "http").
  dynamic "backend" {
    for_each = var.instance_groups
    content {
      group           = backend.value
      balancing_mode  = "UTILIZATION"
      max_utilization = 0.8
      capacity_scaler = 1.0
    }
  }
}

resource "google_compute_url_map" "this" {
  name            = "${var.name_prefix}-url-map"
  default_service = google_compute_backend_service.this.id
}

resource "google_compute_target_http_proxy" "this" {
  name    = "${var.name_prefix}-http-proxy"
  url_map = google_compute_url_map.this.id
}

resource "google_compute_global_forwarding_rule" "http" {
  name                  = "${var.name_prefix}-http"
  ip_address            = google_compute_global_address.this.id
  port_range            = "80"
  target                = google_compute_target_http_proxy.this.id
  load_balancing_scheme = "EXTERNAL_MANAGED"
}
