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

web_zones        = ["us-central1-a", "us-central1-b"]
web_min_replicas = 3
web_max_replicas = 6
