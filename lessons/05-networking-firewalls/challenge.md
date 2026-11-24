# Lesson 05 Challenge — Defense in depth

The security review came back with four findings.

```powershell
python course.py check 05 --challenge
```

| ID | Finding → requirement |
|---|---|
| C5.1 | *"Anyone who can edit a VM can tag it `web` and reach the API."* Allow web → app:8080 by **service account** (`source_service_accounts` / `target_service_accounts`). No tag-based web → app rule may remain. |
| C5.2 | *"A compromised API server could exfiltrate data anywhere."* Lock down app-tier **egress**: deny everything, except TCP 443 to `199.36.153.8/30` (`private.googleapis.com`, Google APIs over a private VIP). The web tier's egress must be unaffected, and web → app must still work. |
| C5.3 | *"We can't investigate incidents."* Enable firewall rule logging on every rule. |
| C5.4 | *"Nobody knows why rule X exists."* Every rule has a `description`. |

## Hints

- Egress rules use `direction = "EGRESS"` and `destination_ranges`.
- Use **priority** to make a narrow allow beat a broad deny. Which number should be smaller?
- `deny { protocol = "all" }` matches every protocol.
- Your egress rules can target the app tier by service account too.

## Beyond the course

Reaching `private.googleapis.com` also requires DNS. A private Cloud DNS zone
for `googleapis.com` would point at those IPs. Lesson 18 covers DNS architecture,
and lesson 19 adds VPC Service Controls for exfiltration protection at the API layer.
