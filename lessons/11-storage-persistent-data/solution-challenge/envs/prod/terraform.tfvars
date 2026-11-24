project_id  = "meridian-prod-7730"
environment = "prod"

# 10.20.0.0/16 never overlaps dev (10.10.0.0/16), so the two can be peered later.
subnets = {
  web = "10.20.1.0/24"
  app = "10.20.2.0/24"
}

ops_subnets = {
  tools = "10.120.0.0/24"
}

web_zones        = ["us-central1-a", "us-central1-b", "us-central1-c"]
web_min_replicas = 3
web_max_replicas = 6

ci_impersonators = ["group:meridian-platform@meridianbooks.example"]

# Production: developers can read logs, nothing more.
developer_groups = {
  "group:meridian-developers@meridianbooks.example" = ["roles/logging.viewer"]
}

backup_retention_days   = 30
snapshot_retention_days = 14
