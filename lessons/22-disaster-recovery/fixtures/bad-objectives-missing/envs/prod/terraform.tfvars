project_id  = "meridian-prod-7730"
environment = "prod"

# 10.20.0.0/16 never overlaps dev (10.10.0.0/16), so the two can be peered later.
subnets = {
  web        = "10.20.1.0/24"
  app        = "10.20.2.0/24"
  serverless = "10.20.3.0/24"  # Direct VPC egress IPs for Cloud Run
  gke        = "10.20.32.0/22" # GKE nodes
}

secondary_ranges = {
  gke = {
    pods     = "10.21.0.0/17"
    services = "10.21.128.0/22"
  }
}

ops_subnets = {
  tools = "10.120.0.0/24"
}

web_zones        = ["us-central1-a", "us-central1-b", "us-central1-c"]
web_min_replicas = 6 # 4 must survive the loss of any one zone
web_max_replicas = 6

app_zones        = ["us-central1-a", "us-central1-b", "us-central1-c"]
app_min_replicas = 3
app_max_replicas = 6

ci_impersonators = ["group:meridian-platform@meridianbooks.example"]

# Production: developers can read logs, nothing more.
developer_groups = {
  "group:meridian-developers@meridianbooks.example" = ["roles/logging.viewer"]
}

backup_retention_days   = 30
snapshot_retention_days = 14

psa_range_address    = "10.20.16.0"
db_tier              = "db-custom-2-7680"
db_availability_type = "REGIONAL"
db_retained_backups  = 14

catalog_image         = "us-central1-docker.pkg.dev/meridian-prod-7730/meridian/catalog@sha256:4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f"
catalog_min_instances = 1

project_number             = "507218934411"
order_worker_image         = "us-central1-docker.pkg.dev/meridian-prod-7730/meridian/order-worker@sha256:7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a"
order_worker_max_instances = 10

gke_master_cidr     = "172.16.1.0/28"
gke_release_channel = "STABLE"

github_repository = "meridianbooks/infrastructure"

oncall_email         = "oncall-prod@meridianbooks.example"
audit_retention_days = 400

hub_network_id = "projects/meridian-net-hub-3300/global/networks/meridian-hub-vpc"

# ---- Disaster recovery (lesson 22): survive the loss of us-central1
dr_region         = "us-east1"
storage_location  = "NAM4" # dual-region: us-central1 + us-east1
turbo_replication = true
registry_location = "us"

