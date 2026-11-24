# Observability for Meridian: know when the shop is broken before customers tell you,
# and keep an audit trail nobody can quietly delete.

resource "google_monitoring_notification_channel" "oncall" {
  display_name = "Meridian on-call (${var.environment})"
  type         = "email"
  labels = {
    email_address = var.oncall_email
  }
}

# --- Is the storefront up? (probed from several continents) -------------------
resource "google_monitoring_uptime_check_config" "storefront" {
  display_name = "meridian-${var.environment}-storefront"
  timeout      = "10s"
  period       = "60s"
  checker_type = "STATIC_IP_CHECKERS"

  http_check {
    path         = "/"
    port         = 80
    use_ssl      = false
    validate_ssl = false
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = var.lb_ip
    }
  }
}

locals {
  runbook_base = "https://wiki.meridianbooks.example/runbooks"
}

resource "google_monitoring_alert_policy" "storefront_down" {
  display_name = "Storefront unreachable (${var.environment})"
  combiner     = "OR"
  severity     = "CRITICAL"
  enabled      = true

  conditions {
    display_name = "Uptime check failing"
    condition_threshold {
      filter          = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND resource.type=\"uptime_url\" AND metric.label.check_id=\"${google_monitoring_uptime_check_config.storefront.uptime_check_id}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 1
      duration        = "120s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_NEXT_OLDER"
        cross_series_reducer = "REDUCE_COUNT_FALSE"
        group_by_fields      = ["resource.label.host"]
      }
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = <<-EOT
      The storefront failed uptime checks from more than one location for 2 minutes.

      1. Check the load balancer backend health (web MIG) in the console.
      2. Check recent deploys in the GitHub Actions history.
      3. Runbook: ${local.runbook_base}/storefront-down
    EOT
  }

  notification_channels = [google_monitoring_notification_channel.oncall.id]

  alert_strategy {
    auto_close = "1800s"
  }
}

# --- Are users getting errors? (5xx share of all load balancer requests) -------
resource "google_monitoring_alert_policy" "lb_5xx" {
  display_name = "Storefront 5xx ratio above 5% (${var.environment})"
  combiner     = "OR"
  severity     = "ERROR"
  enabled      = true

  conditions {
    display_name = "5xx / all requests > 5% for 5 minutes"
    condition_threshold {
      filter             = "metric.type=\"loadbalancing.googleapis.com/https/request_count\" AND resource.type=\"https_lb_rule\" AND metric.label.response_code_class=\"500\""
      denominator_filter = "metric.type=\"loadbalancing.googleapis.com/https/request_count\" AND resource.type=\"https_lb_rule\""
      comparison         = "COMPARISON_GT"
      threshold_value    = 0.05
      duration           = "300s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
      }

      denominator_aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = <<-EOT
      More than 5% of storefront requests return 5xx.

      1. Which backend? Split the metric by backend (web MIG vs /api Cloud Run).
      2. Check Cloud Run and NGINX logs for the first errors.
      3. Runbook: ${local.runbook_base}/storefront-5xx
    EOT
  }

  notification_channels = [google_monitoring_notification_channel.oncall.id]
}

# --- Are orders getting stuck? (lesson 14's dead-letter subscription) -----------
resource "google_monitoring_alert_policy" "dead_letters" {
  display_name = "Order events dead-lettered (${var.environment})"
  combiner     = "OR"
  severity     = "WARNING"
  enabled      = true

  conditions {
    display_name = "Undelivered messages in the dead-letter subscription"
    condition_threshold {
      filter          = "metric.type=\"pubsub.googleapis.com/subscription/num_undelivered_messages\" AND resource.type=\"pubsub_subscription\" AND resource.label.subscription_id=\"${var.dead_letter_subscription}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = <<-EOT
      Order events failed 5 deliveries and were dead-lettered.

      1. Pull a message: `gcloud pubsub subscriptions pull ${var.dead_letter_subscription} --limit=5`
      2. Fix the worker, then replay the messages to the orders topic.
      3. Runbook: ${local.runbook_base}/order-dead-letters
    EOT
  }

  notification_channels = [google_monitoring_notification_channel.oncall.id]
}

# --- Errors as a metric (graph them, alert on them) -----------------------------
resource "google_logging_metric" "worker_errors" {
  name   = "meridian/${var.environment}/order_worker_errors"
  filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${var.worker_service_name}\" AND severity>=ERROR"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

# --- Who read the secrets? (Data Access audit logs are off by default) -----------
resource "google_project_iam_audit_config" "secret_manager" {
  project = var.project_id
  service = "secretmanager.googleapis.com"

  audit_log_config {
    log_type = "DATA_READ"
  }

  audit_log_config {
    log_type = "ADMIN_READ"
  }
}

# --- Keep audit logs where nobody can delete them early ------------------------
resource "google_storage_bucket" "audit" {
  name          = "${var.project_id}-audit-logs"
  location      = upper(var.region)
  storage_class = "STANDARD"

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  retention_policy {
    retention_period = var.audit_retention_days * 86400
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  labels = var.labels

  dynamic "encryption" {
    for_each = var.kms_key_id == null ? [] : [var.kms_key_id]
    content {
      default_kms_key_name = encryption.value
    }
  }
}

resource "google_logging_project_sink" "audit" {
  name        = "meridian-${var.environment}-audit-to-gcs"
  destination = "storage.googleapis.com/${google_storage_bucket.audit.name}"
  filter      = "logName:\"cloudaudit.googleapis.com\""

  # The sink gets its own service account - grant it on this bucket only.
  unique_writer_identity = true
}

resource "google_storage_bucket_iam_member" "audit_writer" {
  bucket = google_storage_bucket.audit.name
  role   = "roles/storage.objectCreator"
  member = google_logging_project_sink.audit.writer_identity
}
