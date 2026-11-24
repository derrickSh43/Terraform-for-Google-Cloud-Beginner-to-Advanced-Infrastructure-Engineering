# Tests modules/observability on its own.
mock_provider "google" {}

variables {
  project_id               = "test-project"
  environment              = "test"
  region                   = "us-central1"
  oncall_email             = "oncall@example.com"
  lb_ip                    = "203.0.113.10"
  dead_letter_subscription = "orders-dead-letter-inspect"
  worker_service_name      = "meridian-order-worker"
  sql_instance_name        = "test-pg"
  labels                   = { app = "meridian", env = "test", managed_by = "terraform" }
}

run "every_alert_has_a_channel" {
  command = plan

  module {
    source = "../../modules/observability"
  }

  assert {
    condition     = google_monitoring_uptime_check_config.storefront.monitored_resource[0].labels["host"] == "203.0.113.10"
    error_message = "The uptime check must probe the load balancer IP."
  }
}

run "missing_at_sign_rejected" {
  command = plan

  module {
    source = "../../modules/observability"
  }

  variables {
    oncall_email = "oncall.example.com"
  }

  expect_failures = [var.oncall_email]
}

run "missing_domain_rejected" {
  command = plan

  module {
    source = "../../modules/observability"
  }

  variables {
    oncall_email = "oncall@"
  }

  expect_failures = [var.oncall_email]
}
