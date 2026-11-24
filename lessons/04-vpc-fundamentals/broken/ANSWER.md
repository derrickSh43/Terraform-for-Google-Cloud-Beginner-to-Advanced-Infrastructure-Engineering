# Answer — Troubleshooting 04

**Symptom:** R4.4: `10.10.1.10/24 has host bits set`.

**Root cause:** a CIDR range is written as its **network address** plus a prefix.
For a /24, the last 8 bits are the host part and must be zero in the network
address. `10.10.1.10/24` names a *host* inside `10.10.1.0/24`, not a network.
The Compute API rejects it.

**Fix:** `default = "10.10.1.0/24"`.

**By hand:** `10.10.1.0/24` → network `10.10.1.0`, broadcast `10.10.1.255`, 256
addresses. Google Cloud reserves **4** per primary range: the network address
(`.0`), the default gateway (`.1`), the second-to-last address (`.254`, reserved
for future use) and the broadcast address (`.255`). That leaves 252 usable addresses.

**Prevention:**

```hcl
validation {
  condition     = can(cidrnetmask(var.web_subnet_cidr)) && cidrhost(var.web_subnet_cidr, 0) == split("/", var.web_subnet_cidr)[0]
  error_message = "web_subnet_cidr must be a network address, e.g. 10.10.1.0/24 (host bits zero)."
}
```
