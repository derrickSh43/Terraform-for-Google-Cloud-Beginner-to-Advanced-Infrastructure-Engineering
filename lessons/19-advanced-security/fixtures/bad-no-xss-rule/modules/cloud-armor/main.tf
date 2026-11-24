# Cloud Armor: a web application firewall at Google's edge, in front of the
# load balancer backends. Rules are evaluated by priority (lowest number first).

resource "google_compute_security_policy" "this" {
  name        = var.name
  description = "Meridian edge protection: OWASP rules and per-client rate limits."
  type        = "CLOUD_ARMOR"

  rule {
    priority    = 1000
    action      = "deny(403)"
    description = "SQL injection (OWASP CRS)"
    match {
      expr {
        expression = "evaluatePreconfiguredWaf('sqli-v33-stable', {'sensitivity': 1})"
      }
    }
  }

  # No single client may send more than var.requests_per_minute requests a minute.
  rule {
    priority    = 2000
    action      = "throttle"
    description = "Per-IP rate limit"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"
      rate_limit_threshold {
        count        = var.requests_per_minute
        interval_sec = 60
      }
    }
  }

  rule {
    priority    = 2147483647
    action      = "allow"
    description = "Default: allow"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
  }
}
