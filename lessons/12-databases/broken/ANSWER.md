# Answer — Troubleshooting 12

**Symptom:** R12.3: `ipv4_enabled is not false: the instance would get a public IP open to ['0.0.0.0/0']`.

**Root cause:** `ipv4_enabled = true` gave the instance a public IP, and an
`authorized_networks` entry of `0.0.0.0/0` allowed every address on the internet
to open a PostgreSQL connection to it.

**Why it's serious even with a strong password and TLS:**

- The database is now **discoverable and attackable**: constant scanning, brute force, and exploitation of
  any future PostgreSQL or Cloud SQL vulnerability before it's patched.
- Connection floods can exhaust `max_connections` and take the shop down without guessing anything.
- "Temporary" exceptions are rarely reverted. This one shipped to prod's module too, since dev and prod share it.

**Fix:** restore

```hcl
ip_configuration {
  ipv4_enabled    = false
  private_network = var.network_id
  ssl_mode        = "ENCRYPTED_ONLY"
}
```

**Safe developer access:** IAP TCP forwarding to a VM in the VPC (lesson 05), then
`cloud-sql-proxy --private-ip` from there, or a short-lived port-forward through
the bastion. Access is controlled by IAM, logged, and the database never gets a public endpoint.

**Prevention:** the organization policy constraint `sql.restrictPublicIp`
blocks public IPs on Cloud SQL across the organization (lesson 19). In CI, a check
like R12.3 fails the PR before anyone approves it.
