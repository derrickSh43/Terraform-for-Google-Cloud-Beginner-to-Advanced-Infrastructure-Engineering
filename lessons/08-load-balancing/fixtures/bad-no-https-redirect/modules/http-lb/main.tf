# Global external Application Load Balancer, assembled from its parts:
#
#   address -> forwarding rule -> target proxy -> URL map -> backend service -> instance group -> VMs
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

# Unmanaged instance group: a named list of existing VMs in one zone.
# Lesson 09 replaces it with a managed instance group that creates VMs itself.
resource "google_compute_instance_group" "this" {
  name      = "${var.name_prefix}-web-ig"
  zone      = var.zone
  instances = var.instances

  named_port {
    name = "http"
    port = var.port
  }
}

resource "google_compute_backend_service" "this" {
  name                  = "${var.name_prefix}-web-backend"
  protocol              = "HTTP"
  port_name             = "http" # must match the instance group's named_port
  load_balancing_scheme = "EXTERNAL_MANAGED"
  timeout_sec           = 30
  health_checks         = [google_compute_health_check.this.id]

  # Let in-flight requests finish before a VM is removed.
  connection_draining_timeout_sec = 30

  log_config {
    enable      = true
    sample_rate = 0.5
  }

  backend {
    group           = google_compute_instance_group.this.id
    balancing_mode  = "UTILIZATION"
    capacity_scaler = 1.0
  }
}

resource "google_compute_url_map" "this" {
  name            = "${var.name_prefix}-url-map"
  default_service = google_compute_backend_service.this.id
}

# With HTTPS on, port 80 only redirects; otherwise it serves the site.
resource "google_compute_url_map" "https_redirect" {
  count = var.enable_https ? 1 : 0

  name = "${var.name_prefix}-https-redirect"

  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    strip_query            = false
  }
}

resource "google_compute_target_http_proxy" "this" {
  name    = "${var.name_prefix}-http-proxy"
  url_map = google_compute_url_map.this.id
}

resource "google_compute_managed_ssl_certificate" "this" {
  count = var.enable_https ? 1 : 0

  name = "${var.name_prefix}-cert"

  managed {
    domains = var.domains
  }
}

resource "google_compute_target_https_proxy" "this" {
  count = var.enable_https ? 1 : 0

  name             = "${var.name_prefix}-https-proxy"
  url_map          = google_compute_url_map.this.id
  ssl_certificates = [google_compute_managed_ssl_certificate.this[0].id]
}

resource "google_compute_global_forwarding_rule" "https" {
  count = var.enable_https ? 1 : 0

  name                  = "${var.name_prefix}-https"
  ip_address            = google_compute_global_address.this.id # same IP as port 80
  port_range            = "443"
  target                = google_compute_target_https_proxy.this[0].id
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

resource "google_compute_global_forwarding_rule" "http" {
  name                  = "${var.name_prefix}-http"
  ip_address            = google_compute_global_address.this.id
  port_range            = "80"
  target                = google_compute_target_http_proxy.this.id
  load_balancing_scheme = "EXTERNAL_MANAGED"
}
