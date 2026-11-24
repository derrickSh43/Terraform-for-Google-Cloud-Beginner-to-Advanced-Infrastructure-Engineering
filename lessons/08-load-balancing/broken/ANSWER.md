# Answer — Troubleshooting 08

**Symptom:** R8.5: `Google health checker -> web VM:80 should be ALLOWED, but is
DENIED (implied ingress deny rule)`.

**Root cause:** `allow-google-lb` only allows `35.191.0.0/16`. Google's front ends
and health checkers also use `130.211.0.0/22`. Probes from that range are
silently dropped by the implied deny rule.

**Why intermittent:** health checks and proxied requests come from **many**
prober and proxy instances spread across both ranges. Some probes succeed, some
time out. The VM keeps crossing the healthy/unhealthy thresholds, and while
it's marked unhealthy the backend has nothing to serve, so clients get 502. Partial
firewall coverage is one of the most common causes of "flapping" backends.

**Fix:**

```hcl
source_ranges = ["130.211.0.0/22", "35.191.0.0/16"]
```

**Prevention:** define the ranges once, e.g. a `google_lb_ranges` output or a
default in the `http-lb` module, which can also own the firewall rule. The module
then always knows exactly which sources its backends must accept. Don't copy
ranges from blog posts. Link the Google Cloud documentation in a comment next to them.
