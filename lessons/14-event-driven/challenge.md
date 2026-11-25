# Lesson 14 Challenge — Contracts, replay and routing

```powershell
python course.py check 14 --challenge
```

| ID | Requirement |
|---|---|
| C14.1 | **Schema-validated events.** Add a `google_pubsub_schema` (AVRO, with a `type` and an optional `order_id`) and attach it to the topic with `schema_settings { encoding = "JSON" }`. Malformed messages are rejected at publish time, not discovered in the worker. |
| C14.2 | **Replay.** Keep 24 h of messages on the topic itself (`message_retention_duration = "86400s"`). After a bad deploy, a subscription can *seek* back and reprocess. |
| C14.3 | **Route by event type.** The worker should only receive `order.created` and `reconcile` events. Add a subscription `filter` on `attributes.event_type`. |
| C14.4 | **Validated attempts.** `max_delivery_attempts` must be 5–100 (Pub/Sub's own limits). `tests/challenge/event_pipeline.tftest.hcl` also checks that the service agent address is built from the project number. |

## Contract for the lesson test

The test calls the module on its own with `topic_name`, `project_number`, `region`, `push_endpoint` and `labels`, so every other
variable needs a default. It looks for `google_pubsub_subscription.push` and
`google_pubsub_topic_iam_member.agent_publishes_dead_letters`.

## Think about it

- Adding a schema to a **deployed** topic forces Terraform to replace it. What happens to unacknowledged messages, and how would you roll that out safely?
- With a filter, where do `order.cancelled` events go? Who should consume them?
