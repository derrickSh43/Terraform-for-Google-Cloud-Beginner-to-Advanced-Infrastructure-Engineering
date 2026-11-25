# Lesson 08 Lab — Put the storefront behind a load balancer

```powershell
python course.py start 08
python course.py check 08
```

The starter is the lesson 07 solution, plus `modules/http-lb/main.tf` (empty)
and `state/dev.tfstate` (dev as deployed after lesson 07). R8.7 and R8.10 are
guard rails that already pass. Keep them green.

---

## Part A — The load balancer module (R8.1 – R8.4)

### Step 1: expose what a load balancer needs from `vm-service`

Add two outputs (with descriptions) to `modules/vm-service/outputs.tf`:
`self_link` (`google_compute_instance.this.self_link`) and `zone`.

### Step 2: build `modules/http-lb`

Inputs: `name_prefix`, `zone`, `instances` (list of VM self links), `port`
(default 80), `health_check_path` (default `"/"`). Name the forwarding rule `http`
and every other resource `this` (`google_compute_url_map.this` and so on). Build the chain back to front:

1. `google_compute_health_check`: `http_health_check { port = var.port  request_path = var.health_check_path }`,
   interval 10 s, timeout 5 s, unhealthy threshold 3.
2. `google_compute_instance_group`: `zone`, `instances = var.instances`,
   `named_port { name = "http"  port = var.port }`.
3. `google_compute_backend_service`: `protocol = "HTTP"`, `port_name = "http"`,
   `load_balancing_scheme = "EXTERNAL_MANAGED"`, `health_checks = [...]`,
   and a `backend { group = google_compute_instance_group.this.id }`.
4. `google_compute_url_map` with `default_service` = the backend service.
5. `google_compute_target_http_proxy` with `url_map`.
6. `google_compute_global_address`, then `google_compute_global_forwarding_rule`:
   `ip_address` = the address, `port_range = "80"`, `target` = the proxy,
   `load_balancing_scheme = "EXTERNAL_MANAGED"`.

Output `ip_address` (`google_compute_global_address.this.address`).

### Step 3: call it

In both environments:

```hcl
module "lb" {
  source = "../../modules/http-lb"

  name_prefix = local.name_prefix
  zone        = module.web.zone
  instances   = [module.web.self_link]
}
```

Run the check. R8.1–R8.4 should pass. If R8.2 fails, it lists the broken link in the chain.

## Part B — Close the side door (R8.5 – R8.7, R8.9)

### Step 4: firewall for Google, not the world

In the firewall map, replace `allow-http` (0.0.0.0/0) with:

```hcl
"allow-google-lb" = {
  description   = "Google Front Ends and health checkers to the web tier."
  source_ranges = ["130.211.0.0/22", "35.191.0.0/16"]
  target_tags   = ["web"]
  ports         = ["80"]
}
```

### Step 5: drop the web VM's public IP

`external_ip = false` on `module "web"`. The VM keeps outbound access through
Cloud NAT. R8.7 confirms that with the connectivity model.

### Step 6: point the outputs at the load balancer

In both environments, replace `web_external_ip` with `lb_ip = module.lb.ip_address`, and build
`web_url` from it. Don't skip this one: `web_url` was built from the IP you just removed, so the plan
fails until you do.

## Part C — Review (R8.8, R8.10)

Read the dev plan (`python course.py check 08 -v`). It should be **8 to
add, 1 to change, 1 to destroy**. Before you accept it, answer:

- Which resource is changed in place, and what changes about it?
- Which resource is destroyed? Is that intended?
- Is anything **replaced** (`-/+`)? It shouldn't be.

## Reflection questions

1. Between "web VM has a public IP" and "load balancer is serving", is there a window where the shop is down? How would you order a real rollout? (Hint: `terraform apply -target`, or two PRs.)
2. Why must the health check use the same port as the named port?
3. A user's real IP no longer shows up in NGINX logs. Where can you find it? (Look up `X-Forwarded-For`.)
4. The instance group is **zonal**. What happens to the load balancer if `us-central1-a` fails? (Lesson 09 answers this.)
