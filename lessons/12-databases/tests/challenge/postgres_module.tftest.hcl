# Tests modules/postgres on its own.
mock_provider "google" {}
mock_provider "random" {}

variables {
  name_prefix = "test"
  region      = "us-central1"
  network_id  = "projects/test-project/global/networks/test-vpc"
  labels      = { app = "meridian", env = "test", managed_by = "terraform" }
}

run "dev_defaults_are_private_and_backed_up" {
  command = plan

  module {
    source = "../../modules/postgres"
  }

  assert {
    condition     = google_sql_database_instance.this.settings[0].ip_configuration[0].ipv4_enabled == false
    error_message = "The instance must never get a public IP."
  }

  assert {
    condition     = google_sql_database_instance.this.settings[0].backup_configuration[0].point_in_time_recovery_enabled
    error_message = "PITR must be on by default."
  }
}

run "regional_on_dedicated_tier_is_fine" {
  command = plan

  module {
    source = "../../modules/postgres"
  }

  variables {
    tier              = "db-custom-2-7680"
    availability_type = "REGIONAL"
  }
}

run "regional_on_shared_core_is_rejected" {
  command = plan

  module {
    source = "../../modules/postgres"
  }

  variables {
    tier              = "db-g1-small"
    availability_type = "REGIONAL"
  }

  expect_failures = [var.availability_type]
}
