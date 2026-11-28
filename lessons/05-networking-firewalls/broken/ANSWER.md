# Answer — Troubleshooting 05

**Symptom:** R5.8: `web VM -> app VM:8080/tcp should be ALLOWED, but is DENIED (implied ingress deny rule)`.

**Root cause:** in `firewall.tf`, `allow_web_to_app` has `target_tags = ["api"]`,
but the app VM in `app.tf` is tagged `app`. Someone wrote the name of the
*service* ("the API") instead of the VM's *tag*. No VM has the tag `api`, so the
rule is valid, it plans and applies, and it applies to no VM at all. Traffic falls
through to the implied deny-ingress rule.

**Why a timeout:** a firewall *drops* packets silently. The client keeps
retransmitting SYNs until it gives up. "Connection refused" means the packet
**arrived** and nothing was listening on the port, which is a different problem.

**Fix:** `target_tags = ["app"]`.

**Prevention:** referencing identities instead of free-text strings, as in
challenge C5.1 (`target_service_accounts = [google_service_account.app.email]`),
turns this kind of typo into a `terraform validate` error: *Reference to undeclared
resource*. A tag is just a string, so Terraform can never check that a VM carries it.
