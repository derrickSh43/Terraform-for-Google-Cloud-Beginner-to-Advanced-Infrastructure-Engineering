# Order events: publish once, process reliably.
#
#   API ──publish──► orders topic ──push (OIDC)──► order-worker (Cloud Run)
#                         │ after N failed deliveries
#                         ▼
#                  orders-dead-letter topic ──► pull subscription (inspect / replay)

locals {
  # Google-managed identity that Pub/Sub uses to move messages to the dead-letter topic.
  pubsub_agent = "serviceAccount:service-${var.project_number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_topic" "events" {
  name   = var.topic_name
  labels = var.labels
}

resource "google_pubsub_topic" "dead_letter" {
  name   = "${var.topic_name}-dead-letter"
  labels = var.labels
}

# The identity Pub/Sub presents to the worker (OIDC token on every push).
resource "google_service_account" "push" {
  account_id   = "meridian-${var.topic_name}-push"
  display_name = "Pub/Sub push to ${var.topic_name} worker"
}

resource "google_pubsub_subscription" "push" {
  name                 = "${var.topic_name}-to-worker"
  topic                = google_pubsub_topic.events.id
  ack_deadline_seconds = 60
  labels               = var.labels

  message_retention_duration = "604800s" # 7 days to recover from a worker outage

  push_config {
    push_endpoint = var.push_endpoint

    oidc_token {
      service_account_email = google_service_account.push.email
      audience              = var.push_endpoint
    }
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = var.max_delivery_attempts
  }

  expiration_policy {
    ttl = "" # never expire, even if no messages flow for weeks
  }
}

# Failed messages must land somewhere readable, or they're gone.
resource "google_pubsub_subscription" "dead_letter" {
  name                       = "${var.topic_name}-dead-letter-inspect"
  topic                      = google_pubsub_topic.dead_letter.id
  message_retention_duration = "604800s"
  labels                     = var.labels

  expiration_policy {
    ttl = ""
  }
}

# --- Permissions the dead-letter mechanism needs ------------------------------
resource "google_pubsub_topic_iam_member" "agent_publishes_dead_letters" {
  topic  = google_pubsub_topic.dead_letter.id
  role   = "roles/pubsub.publisher"
  member = local.pubsub_agent
}

resource "google_pubsub_subscription_iam_member" "agent_acks_source" {
  subscription = google_pubsub_subscription.push.id
  role         = "roles/pubsub.subscriber"
  member       = local.pubsub_agent
}

# Pub/Sub mints OIDC tokens for the push identity.
resource "google_service_account_iam_member" "agent_mints_push_tokens" {
  service_account_id = google_service_account.push.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = local.pubsub_agent
}

# --- Who may publish -----------------------------------------------------------
resource "google_pubsub_topic_iam_member" "publishers" {
  for_each = toset(var.publishers)

  topic  = google_pubsub_topic.events.id
  role   = "roles/pubsub.publisher"
  member = each.value
}

# --- Nightly reconciliation event ---------------------------------------------
resource "google_cloud_scheduler_job" "nightly" {
  name      = "${var.topic_name}-nightly-reconcile"
  region    = var.region
  schedule  = "0 2 * * *"
  time_zone = "America/Chicago"

  pubsub_target {
    topic_name = google_pubsub_topic.events.id
    data       = base64encode(jsonencode({ type = "reconcile" }))
    attributes = {
      event_type = "reconcile"
    }
  }

  retry_config {
    retry_count = 3
  }
}
