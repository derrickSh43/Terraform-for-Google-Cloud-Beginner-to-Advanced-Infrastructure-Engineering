# Answer — Troubleshooting 07

**Symptom:** R7.3: `app VM has no external IP and no Cloud NAT covers meridian-dev-app`.

**Root cause:** the NAT was switched to `LIST_OF_SUBNETWORKS` with a single
`subnetwork` block for `this["web"]`. The web VM has an **external IP**, and VMs
with external IPs never use Cloud NAT. So the NAT now serves no VM at all, while the
app subnet, the only one that needs it, lost its path to the internet.

**Fix:** list the app subnet instead, or go back to
`ALL_SUBNETWORKS_ALL_IP_RANGES`:

```hcl
subnetwork {
  name                    = google_compute_subnetwork.this["app"].id
  source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
}
```

**Guard:** the challenge's `nat_subnets` variable, with its validation and the
environment passing `["app"]`, makes the intent explicit and reviewable. A
connectivity check like R7.3 in CI (lesson 16) catches the regression before merge.

**Lesson:** "the gateway is healthy" says nothing about *which traffic it
serves*. When debugging egress, ask in order: does the VM have an external IP?
Is there a NAT in **its** region and network? Does that NAT include **its** subnet?
Do egress firewall rules allow it?
