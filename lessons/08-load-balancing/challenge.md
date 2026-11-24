# Lesson 08 Challenge — HTTPS done properly

```powershell
python course.py check 08 --challenge
```

| ID | Requirement |
|---|---|
| C8.1 | Serve HTTPS on **443** with a `google_compute_managed_ssl_certificate` (domains from a variable). Add a `google_compute_target_https_proxy` and a second forwarding rule that uses the **same** reserved address. Dev uses `dev.meridianbooks.example`, prod `www.meridianbooks.example`. |
| C8.2 | Port 80 must **redirect** to HTTPS, not serve the site: a second URL map with `default_url_redirect { https_redirect = true }`, used by the HTTP proxy. |
| C8.3 | Backend operations: request logging (`log_config`, sample rate 0.5) and an explicit `connection_draining_timeout_sec` of 10–60 s. The provider default is 300 s, which slows every rollout. |
| C8.4 | Make HTTPS a module option: `enable_https` (default `false`) and `domains`. With it off, the module builds exactly what the lab did. `tests/challenge/http_lb_module.tftest.hcl` tests both modes against the module directly. |

## Hints

- Optional resources: `count = var.enable_https ? 1 : 0`, referenced as `google_compute_target_https_proxy.this[0].id`.
- The HTTP proxy's URL map becomes conditional:
  `url_map = var.enable_https ? google_compute_url_map.https_redirect[0].id : google_compute_url_map.this.id`.
- Update `web_url` to `https://<your domain>`.

## Think about it

The certificate stays `PROVISIONING` until DNS for the domain points at the
load balancer IP. What does that mean for the order of operations in a brand-new
environment? Which output does the DNS team need first?
