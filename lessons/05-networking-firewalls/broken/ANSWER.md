# Answer — Troubleshooting 05

**Symptom:** R5.8: `web VM -> app VM:8080/tcp should be ALLOWED, but is DENIED (implied ingress deny rule)`.

**Root cause:** `allow_web_to_app` has `target_tags = ["api"]`, but the app VM is
tagged `app`. The rule is valid, it plans and applies, and it protects no VM at
all. So traffic falls through to the implied deny-ingress rule.

**Why a timeout:** a firewall *drops* packets silently. The client keeps
retransmitting SYNs until it gives up. "Connection refused" means the packet
**arrived** and nothing was listening on the port, which is a different problem.

**Fix:** `target_tags = ["app"]`.

**Prevention:** referencing identities instead of free-text strings, as in
challenge C5.1 (`target_service_accounts = [google_service_account.app.email]`),
turns this typo into a `terraform validate` error: *Reference to undeclared resource*.
A string tag can never be checked that way.
