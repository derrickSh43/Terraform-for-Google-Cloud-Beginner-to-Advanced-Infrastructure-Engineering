# Lesson 13 Lab — The catalog API on Cloud Run

```powershell
python course.py start 13
python course.py check 13
```

The starter is the lesson 12 solution plus two empty modules,
`modules/artifact-repo` and `modules/cloud-run-service`, and `state/dev.tfstate`
(dev after lesson 12). R13.9 is a guard rail: additions and in-place changes only.

---

## Part A — Registry (R13.1, R13.2)

1. Add `run.googleapis.com` and `artifactregistry.googleapis.com` to the foundation APIs.
2. In `modules/artifact-repo`: a `google_artifact_registry_repository` (`format = "DOCKER"`,
   `location = var.region`) with two `cleanup_policies`:
   `DELETE` with `condition { tag_state = "UNTAGGED"  older_than = "2592000s" }` and
   `KEEP` with `most_recent_versions { keep_count = 10 }`. Set `cleanup_policy_dry_run = false`.
3. `google_artifact_registry_repository_iam_member` per `var.writers`, with `roles/artifactregistry.writer`.
   The environments pass `["serviceAccount:${module.ci.email}"]`.

## Part B — The service (R13.3 – R13.7)

In `modules/cloud-run-service`:

1. `google_service_account` `meridian-${var.name}`.
2. `google_cloud_run_v2_service`:
   - `ingress = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"`, `invoker_iam_disabled = true`
   - `template.service_account` = the new account, `max_instance_request_concurrency = 80`
   - `scaling { min_instance_count = var.min_instances  max_instance_count = var.max_instances }` (default max 5)
   - one container: `image = var.image`, port 8080, `resources { limits = { cpu = "1", memory = "512Mi" }  cpu_idle = true }`
   - plain env vars from `var.env` and secret env vars from `var.secret_env`. Use two `dynamic "env"` blocks;
     the secret one uses `value_source { secret_key_ref { secret = env.value  version = "latest" } }`
   - `vpc_access { egress = "PRIVATE_RANGES_ONLY"  network_interfaces { network  subnetwork  tags = [var.name] } }`
3. `google_compute_region_network_endpoint_group`: `network_endpoint_type = "SERVERLESS"`,
   `cloud_run { service = google_cloud_run_v2_service.this.name }`.
4. Outputs: `service_account_email`, `neg_id`, `service_name`.

Wiring in the environments:

- add a `serverless` subnet to `subnets` in tfvars (dev `10.10.3.0/24`, prod `10.20.3.0/24`)
- `module "catalog"` with `image = var.catalog_image`, `subnet_id = module.network.subnet_ids["serverless"]`,
  `env = { DB_HOST = module.db.private_ip, ... }`, `secret_env = { DB_PASSWORD = module.db.password_secret_id }`
- add the catalog's service account to `secret_readers` of `module "db"`
- tfvars: `catalog_image` pinned by digest (the starter has an example), `catalog_min_instances` (dev 0, prod 1)

## Part C — Route `/api/*` (R13.8)

In `modules/http-lb`, add `variable "api_neg_id"` and:

```hcl
resource "google_compute_backend_service" "api" {
  name                  = "${var.name_prefix}-api-backend"
  protocol              = "HTTPS"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  backend { group = var.api_neg_id }
}
```

Give the URL map a `host_rule` (`hosts = ["*"]`) and a `path_matcher` whose
`path_rule { paths = ["/api", "/api/*"]  service = google_compute_backend_service.api.id }`.
Its `default_service` stays the web backend. Pass `api_neg_id = module.catalog.neg_id`.

## Review

Dev: **10 to add, 1 to change, 0 to destroy**. Which resource changes in place, and why does that
change not interrupt the shop?

## Reflection questions

1. A teammate pushes a new image as `catalog:latest`. What changes in production? What if prod used `:latest`?
2. Why does `invoker_iam_disabled = true` make sense here but would be dangerous with `INGRESS_TRAFFIC_ALL`?
3. 5 instances × 80 concurrent requests: how many database connections could the catalog open? Why does `max_instance_count` protect Cloud SQL?
4. With `egress = "PRIVATE_RANGES_ONLY"`, how does the service reach the internet, and why doesn't it need Cloud NAT?
