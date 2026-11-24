# Answer — Troubleshooting 17

**Symptom:** R17.1: `Alert policies with no notification channel: [all three]`.

**Root cause:** every `google_monitoring_alert_policy` lost its
`notification_channels`. Alerting still *works*: conditions are evaluated, incidents
open, the console shows them. But an incident with no channel notifies nobody. The
configuration is valid, `terraform plan` is happy, and the dashboard is red while every phone stays silent.

**Fix:** restore

```hcl
notification_channels = [google_monitoring_notification_channel.oncall.id]
```

on each policy.

**Test it before you need it:** the console's *Send test notification* on the channel, and a
periodic fire drill. For example, temporarily point the uptime check at a path that returns 404 in
dev, confirm the page arrives within the expected time, then revert. Better still, route to an
incident tool (PagerDuty, Opsgenie) with escalation, so an unacknowledged page reaches someone else.

**CI guard:** a policy check, exactly like R17.1, that fails the PR when any alert policy has no
notification channel or no runbook (R17.6). Lesson 16's checks job is where it runs.
