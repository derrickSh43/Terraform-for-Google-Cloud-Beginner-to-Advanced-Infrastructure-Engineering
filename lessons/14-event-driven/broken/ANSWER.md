# Answer — Troubleshooting 14

**Symptom:** R14.4: `The Pub/Sub service agent can't publish to the dead-letter topic`.

**Root cause:** dead-lettering is performed by Google's Pub/Sub service agent,
`service-<project number>@gcp-sa-pubsub.iam.gserviceaccount.com`, not by your
code or your service accounts. The broken module removed its
`roles/pubsub.publisher` grant on the dead-letter topic. When a message reaches
`max_delivery_attempts`, Pub/Sub tries to forward it, is denied, and keeps
redelivering it to the worker indefinitely. The configuration *looks* right, but
the mechanism can't run.

**Fix:** both grants, on the right resources:

```hcl
resource "google_pubsub_topic_iam_member" "agent_publishes_dead_letters" {
  topic  = google_pubsub_topic.dead_letter.id      # the DEAD-LETTER topic
  role   = "roles/pubsub.publisher"
  member = local.pubsub_agent
}

resource "google_pubsub_subscription_iam_member" "agent_acks_source" {
  subscription = google_pubsub_subscription.push.id # the SOURCE subscription
  role         = "roles/pubsub.subscriber"
  member       = local.pubsub_agent
}
```

**Why apply succeeds:** the API accepts a `dead_letter_policy` without checking
the agent's permissions. The failure only shows at runtime, as a Pub/Sub warning
in the subscription's details and as "dead letter forwarding" errors in Cloud
Monitoring. Lesson 17 adds an alert on the dead-letter backlog, and on
subscription age, so a stuck pipeline pages someone.
