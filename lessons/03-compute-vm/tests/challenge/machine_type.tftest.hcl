mock_provider "google" {}

run "small_machine_types_are_allowed" {
  command = plan

  variables {
    machine_type = "e2-small"
  }

  assert {
    condition     = google_compute_instance.web.machine_type == "e2-small"
    error_message = "The VM should use var.machine_type."
  }
}

run "large_machine_types_are_rejected" {
  command = plan

  variables {
    machine_type = "n2-standard-8"
  }

  expect_failures = [var.machine_type]
}
