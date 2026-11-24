project_id  = "meridian-dev-4821"
environment = "dev"

subnets = {
  web        = "10.10.1.0/24"
  app        = "10.10.2.0/24"
  serverless = "10.10.3.0/24" # Direct VPC egress IPs for Cloud Run
}

ops_subnets = {
  tools = "10.110.0.0/24"
}

web_zones        = ["us-central1-a", "us-central1-b"]
web_min_replicas = 2
web_max_replicas = 4

ci_impersonators = ["group:meridian-platform@meridianbooks.example"]

developer_groups = {
  "group:meridian-developers@meridianbooks.example" = ["roles/compute.viewer", "roles/logging.viewer"]
}

backup_retention_days   = 7
snapshot_retention_days = 7

psa_range_address    = "10.10.16.0"
db_tier              = "db-g1-small"
db_availability_type = "ZONAL"
db_retained_backups  = 7

catalog_image         = "us-central1-docker.pkg.dev/meridian-dev-4821/meridian/catalog@sha256:4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f"
catalog_min_instances = 0

project_number             = "418273645512"
order_worker_image         = "us-central1-docker.pkg.dev/meridian-dev-4821/meridian/order-worker@sha256:7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a"
order_worker_max_instances = 3
