project_id  = "meridian-dev-4821"
environment = "dev"

subnets = {
  web = "10.10.1.0/24"
  app = "10.10.2.0/24"
}

ops_subnets = {
  tools = "10.110.0.0/24"
}

web_zones        = ["us-central1-a", "us-central1-b"]
web_min_replicas = 1
web_max_replicas = 4
