# Tests modules/event-pipeline on its own.
mock_provider "google" {}

variables {
  topic_name     = "orders"
  project_number = "123456789012"
  region         = "us-central1"
  push_endpoint  = "https://worker-abc-uc.a.run.app/events"
  labels         = { app = "meridian", env = "test", managed_by = "terraform" }
}

run "defaults_dead_letter_after_five" {
  command = plan

  module {
    source = "../../modules/event-pipeline"
  }

  assert {
    condition     = google_pubsub_subscription.push.dead_letter_policy[0].max_delivery_attempts == 5
    error_message = "Default should dead-letter after 5 attempts."
  }

  assert {
    condition     = google_pubsub_topic_iam_member.agent_publishes_dead_letters.member == "serviceAccount:service-123456789012@gcp-sa-pubsub.iam.gserviceaccount.com"
    error_message = "The Pub/Sub service agent address must be built from the project number."
  }
}

run "too_few_attempts_rejected" {
  command = plan

  module {
    source = "../../modules/event-pipeline"
  }

  variables {
    max_delivery_attempts = 2
  }

  expect_failures = [var.max_delivery_attempts]
}

run "too_many_attempts_rejected" {
  command = plan

  module {
    source = "../../modules/event-pipeline"
  }

  variables {
    max_delivery_attempts = 500
  }

  expect_failures = [var.max_delivery_attempts]
}
