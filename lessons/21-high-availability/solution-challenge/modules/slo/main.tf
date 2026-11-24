# The storefront's availability objective, measured at the load balancer:
# the share of requests that don't fail with a 5xx.

locals {
  lb_requests = join(" AND ", [
    "metric.type=\"loadbalancing.googleapis.com/https/request_count\"",
    "resource.type=\"https_lb_rule\"",
    "resource.label.\"forwarding_rule_name\"=\"${var.forwarding_rule_name}\"",
  ])
}

resource "google_monitoring_custom_service" "storefront" {
  service_id   = "${var.name_prefix}-storefront"
  display_name = "Meridian storefront (${var.name_prefix})"
}

resource "google_monitoring_slo" "availability" {
  service             = google_monitoring_custom_service.storefront.service_id
  slo_id              = "availability-28d"
  display_name        = "${var.goal * 100}% of storefront requests succeed (28 days)"
  goal                = var.goal
  rolling_period_days = 28

  request_based_sli {
    good_total_ratio {
      total_service_filter = local.lb_requests
      bad_service_filter   = "${local.lb_requests} AND metric.label.\"response_code_class\"=\"500\""
    }
  }
}

# Fast burn: at this rate the 28-day error budget would be gone in about two
# days. 2% of the budget in one hour = burn rate 0.02 * 28 * 24 = 13.44.
resource "google_monitoring_alert_policy" "fast_burn" {
  display_name = "Storefront SLO fast burn (${var.name_prefix})"
  combiner     = "OR"

  conditions {
    display_name = "2% of the error budget burnt in an hour"

    condition_threshold {
      filter          = "select_slo_burn_rate(\"${google_monitoring_slo.availability.id}\", \"3600s\")"
      comparison      = "COMPARISON_GT"
      threshold_value = 13.44
      duration        = "0s"
    }
  }

  notification_channels = [var.notification_channel]
}
