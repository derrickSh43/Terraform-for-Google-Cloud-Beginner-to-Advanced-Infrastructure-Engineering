# Runs inside modules/kms.
mock_provider "google" {}

variables {
  environment    = "test"
  region         = "us-central1"
  project_number = "123456789012"
  labels         = { app = "meridian", env = "test", managed_by = "terraform" }
}

run "default_rotation_is_90_days" {
  command = plan

  assert {
    condition     = google_kms_crypto_key.storage.rotation_period == "7776000s"
    error_message = "90 days is 7776000 seconds."
  }

  assert {
    condition     = google_kms_crypto_key_iam_member.storage_agent.member == "serviceAccount:service-123456789012@gs-project-accounts.iam.gserviceaccount.com"
    error_message = "The grant must go to the Cloud Storage service agent of this project."
  }
}

run "yearly_rotation_rejected" {
  command = plan

  variables {
    rotation_days = 365
  }

  expect_failures = [var.rotation_days]
}

run "zero_rotation_rejected" {
  command = plan

  variables {
    rotation_days = 0
  }

  expect_failures = [var.rotation_days]
}
