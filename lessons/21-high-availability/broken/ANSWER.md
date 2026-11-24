# Answer — Troubleshooting 21

**Fault:** the health-check firewall rule for the app tier allows port **80**, but the API and both
health checks use **8080**:

```hcl
"allow-health-checks-app" = {
  source_ranges = ["130.211.0.0/22", "35.191.0.0/16"]
  target_tags   = ["app"]
  ports         = ["80"]   # should be "8080"
}
```

1. R21.3 fails: "Health checker 35.191.0.1 -> app:8080 is blocked: implied ingress deny rule".
   `curl localhost` never leaves the VM, so it doesn't go through the VPC firewall. Health checks
   arrive from Google's ranges and are dropped by the implied deny-all ingress rule.
2. The internal load balancer's health check and the MIG's autohealing check both probe 8080 from
   the same ranges. One concludes "send no traffic", the other "this VM is broken, recreate it". The
   new VM boots and fails the same way, forever.
3. Change the port to `"8080"` (in both environments). In the plan, the rule's `allow` block shows
   `ports = ["80"]` next to `port = 8080` on the health checks. Reading it would have caught this, but
   a check like R21.3 that evaluates the path catches it every time.
4. It was copied from `allow-google-lb`, the web tier's rule, which correctly uses port 80. Copied
   blocks keep their old values: a module input like `health_check_port`, used by both the firewall
   rule and the health checks, makes the two impossible to disagree.
