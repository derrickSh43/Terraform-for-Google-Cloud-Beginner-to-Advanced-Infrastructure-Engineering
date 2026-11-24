# Runs inside modules/postgres.
mock_provider "google" {}
mock_provider "random" {}

variables {
  name_prefix = "meridian-test"
  region      = "us-central1"
  network_id  = "projects/test-project/global/networks/test"
  labels      = { app = "meridian" }
}

run "no_replica_by_default" {
  command = plan

  assert {
    condition     = length(google_sql_database_instance.replica) == 0
    error_message = "Without dr_region there must be no replica (dev stays cheap)."
  }
}

run "replica_in_dr_region" {
  command = plan

  variables {
    dr_region = "us-east1"
  }

  assert {
    condition     = google_sql_database_instance.replica[0].region == "us-east1"
    error_message = "The replica belongs in dr_region."
  }

  assert {
    condition     = google_sql_database_instance.replica[0].settings[0].ip_configuration[0].ipv4_enabled == false
    error_message = "The replica must be private, like its primary."
  }
}

run "same_region_rejected" {
  command = plan

  variables {
    dr_region = "us-central1"
  }

  expect_failures = [var.dr_region]
}
