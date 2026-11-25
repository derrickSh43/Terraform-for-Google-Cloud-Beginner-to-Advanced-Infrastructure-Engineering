# Lesson 17 Lab — Know when Meridian is broken

```powershell
python course.py start 17
python course.py check 17
```

The starter is the lesson 16 solution plus an empty `modules/observability` and
`state/dev.tfstate` (dev after lesson 16).

---

## Part A — Channel and uptime (R17.1 – R17.3)

Start by declaring the inputs of `modules/observability` in its `variables.tf` and calling it from both
environments, so every part below is checked as you build it:

```hcl
module "observability" {
  source                   = "../../modules/observability"
  lb_ip                    = module.lb.ip_address
  dead_letter_subscription = module.orders.dead_letter_subscription
  worker_service_name      = module.order_worker.service_name
  # project_id, environment, region, oncall_email, audit_retention_days, labels
}
```

tfvars: `oncall_email` (`oncall-<env>@meridianbooks.example`), `audit_retention_days` (dev 90, prod 400).

Then, in `modules/observability` (inputs: `project_id`, `environment`, `region`, `oncall_email`,
`lb_ip`, `dead_letter_subscription`, `worker_service_name`, `labels`, and `audit_retention_days` with a default):

1. `google_monitoring_notification_channel`, type `email`, `labels = { email_address = var.oncall_email }`.
2. `google_monitoring_uptime_check_config` `storefront`: `period = "60s"`, `timeout = "10s"`,
   `http_check { path = "/"  port = 80 }`, `monitored_resource { type = "uptime_url"  labels = { project_id, host = var.lb_ip } }`.
3. An alert policy on `monitoring.googleapis.com/uptime_check/check_passed` for this check's
   `uptime_check_id`: aggregate with `ALIGN_NEXT_OLDER` + `REDUCE_COUNT_FALSE`, fire when the count is `> 1`
   for `120s`.

## Part B — Error ratio and stuck orders (R17.4 – R17.6)

4. A 5xx **ratio** alert: `filter` = load balancer `request_count` with `response_code_class="500"`,
   `denominator_filter` = all `request_count`, both aggregated with `ALIGN_RATE` + `REDUCE_SUM`
   (`aggregations` and `denominator_aggregations`), `threshold_value = 0.05`, `duration = "300s"`.
5. A dead-letter alert: `pubsub.googleapis.com/subscription/num_undelivered_messages` for
   `resource.label.subscription_id = var.dead_letter_subscription`, `> 0` for `300s`.
6. On **every** policy: `severity`, `documentation` (markdown with first steps and a runbook link),
   `notification_channels`, `enabled = true`.

## Part C — Logs and audit (R17.7 – R17.9)

7. `google_logging_metric` counting the order worker's `severity>=ERROR` entries.
8. `google_project_iam_audit_config` for `secretmanager.googleapis.com` with `DATA_READ` (and `ADMIN_READ`).
9. An audit bucket (`"${var.project_id}-audit-logs"`) with a retention policy of `var.audit_retention_days`
   days, uniform access and public access prevention. Then a `google_logging_project_sink` with
   `filter = "logName:\"cloudaudit.googleapis.com\""` and `unique_writer_identity = true`, plus
   `roles/storage.objectCreator` on the bucket for the sink's `writer_identity`.

## Part D — Review the rollout (R17.10)

Dev: **10 to add, 0 to change, 0 to destroy**. For each alert, ask: would I want to be woken up
by this? What would I do first?

## Reflection questions

1. Why is "5xx ratio > 5%" better than "more than 100 errors per minute"?
2. The uptime check passes but customers report errors. Which alert should catch it, and why might the uptime check miss it?
3. Who can delete an audit log object in the bucket before it is 90 days old?
4. Why `unique_writer_identity = true` instead of letting the sink write as a shared Google identity?
