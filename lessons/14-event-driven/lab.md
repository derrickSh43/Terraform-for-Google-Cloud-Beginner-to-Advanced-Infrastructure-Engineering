# Lesson 14 Lab — Order events with retries and a dead-letter queue

```powershell
python course.py start 14
python course.py check 14
```

The starter is the lesson 13 solution plus an empty `modules/event-pipeline`
and `state/dev.tfstate` (dev after lesson 13). R14.8 and R14.9 are guard rails.

---

## Part A — APIs and a reusable Cloud Run module (R14.1, R14.8)

Add `pubsub.googleapis.com` and `cloudscheduler.googleapis.com` to the foundation module's `apis` default.

Then, in `modules/cloud-run-service`:

1. New variables: `ingress` (default `"INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"`),
   `create_neg` (default `true`), `invokers` (default `[]`).
2. `ingress = var.ingress`, and
   `invoker_iam_disabled = var.ingress == "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER" && length(var.invokers) == 0`.
   The deployed catalog keeps exactly its current settings.
3. `count = var.create_neg ? 1 : 0` on the NEG; output `one(google_compute_region_network_endpoint_group.this[*].id)`.
   Add the (optional, documenting) `moved` block from `...this` to `...this[0]`.
4. `google_cloud_run_v2_service_iam_member` per invoker, with `roles/run.invoker`.
5. Output `uri`.

Run the check. The catalog must not change: R14.8.

## Part B — The pipeline module

Nothing checks this part yet: the pipeline needs the worker's URL, and the worker needs the pipeline's
push identity. Part C wires both, and checks them.

In `modules/event-pipeline` (inputs: `topic_name`, `project_number`, `region`,
`push_endpoint`, `labels`, and with defaults `max_delivery_attempts` = 5, `publishers` = `[]`):

1. `google_pubsub_topic` `events` and `dead_letter` (`"${var.topic_name}-dead-letter"`).
2. A push identity: `google_service_account` `meridian-${var.topic_name}-push`.
3. `google_pubsub_subscription` `push`, on `events`:
   - `push_config { push_endpoint = var.push_endpoint  oidc_token { service_account_email = <push SA>  audience = var.push_endpoint } }`
   - `ack_deadline_seconds = 60`, `message_retention_duration = "604800s"`
   - `retry_policy` 10 s – 600 s, `dead_letter_policy` to the dead-letter topic
   - `expiration_policy { ttl = "" }`
4. A pull subscription on the dead-letter topic (retention 7 days, never expires).
5. The service agent (`"serviceAccount:service-${var.project_number}@gcp-sa-pubsub.iam.gserviceaccount.com"`):
   - `google_pubsub_topic_iam_member` `agent_publishes_dead_letters`: publisher on the **dead-letter topic**
   - `google_pubsub_subscription_iam_member`: subscriber on the **push subscription**
   - `google_service_account_iam_member`: `roles/iam.serviceAccountTokenCreator` on the push SA (it mints the OIDC tokens)
6. `google_pubsub_topic_iam_member` publisher grants for `var.publishers`.
7. `google_cloud_scheduler_job`: `schedule = "0 2 * * *"`, `time_zone = "America/Chicago"`,
   `pubsub_target { topic_name = <events topic id>  data = base64encode(jsonencode({ type = "reconcile" })) }`.

Outputs: `topic_id`, `push_service_account_email`, `dead_letter_subscription`.

## Part C — Wire it up (R14.2 – R14.7, R14.10)

In both environments:

```hcl
module "order_worker" {
  source     = "../../modules/cloud-run-service"
  name       = "order-worker"
  image      = var.order_worker_image
  ingress    = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  create_neg = false
  invokers   = ["serviceAccount:${module.orders.push_service_account_email}"]
  # ... region, network, serverless subnet, DB env + secret_env, max_instances
}

module "orders" {
  source        = "../../modules/event-pipeline"
  topic_name    = "orders"
  push_endpoint = "${module.order_worker.uri}/events"
  publishers    = ["serviceAccount:${module.app.service_account_email}"]
  # ... project_number, region, labels
}
```

Add the worker's service account to `secret_readers` of `module "db"`. New tfvars:
`project_number`, `order_worker_image` (pinned by digest), `order_worker_max_instances` (dev 3, prod 10).

## Review

Dev: **16 to add, 0 to change, 0 to destroy**, and the catalog NEG "has moved". Now
delete the `moved` block and re-run. Does anything change? Read the README section on
Terraform addresses to see why.

## Reflection questions

1. The worker returns HTTP 500 for order 77 every time. Trace exactly what happens to that message, attempt by attempt.
2. Why does the dead-letter topic need its *own* subscription?
3. The worker crashes after updating the database but before returning 200. What happens next, and why must the worker be idempotent?
4. Why grant `run.invoker` to the push identity on the worker service, instead of making the worker public with a secret token in the URL?
