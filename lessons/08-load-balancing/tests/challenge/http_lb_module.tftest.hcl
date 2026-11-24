# Tests modules/http-lb on its own: HTTPS on and off.
mock_provider "google" {}

variables {
  name_prefix = "test"
  zone        = "us-central1-a"
  instances   = ["https://www.googleapis.com/compute/v1/projects/p/zones/us-central1-a/instances/web-1"]
}

run "http_only_by_default" {
  command = plan

  module {
    source = "../../modules/http-lb"
  }

  assert {
    condition     = length(google_compute_global_forwarding_rule.https) == 0
    error_message = "With enable_https = false there must be no port 443 rule."
  }

  assert {
    condition     = length(google_compute_url_map.https_redirect) == 0
    error_message = "With enable_https = false, port 80 must serve the site (no redirect map)."
  }
}

run "https_adds_cert_redirect_and_443" {
  command = plan

  module {
    source = "../../modules/http-lb"
  }

  variables {
    enable_https = true
    domains      = ["shop.example.com"]
  }

  assert {
    condition     = length(google_compute_managed_ssl_certificate.this) == 1
    error_message = "enable_https should create one managed certificate."
  }

  assert {
    condition     = google_compute_global_forwarding_rule.https[0].port_range == "443"
    error_message = "The HTTPS forwarding rule must listen on 443."
  }

  assert {
    condition     = google_compute_url_map.https_redirect[0].default_url_redirect[0].https_redirect == true
    error_message = "Port 80 should redirect to HTTPS."
  }
}
