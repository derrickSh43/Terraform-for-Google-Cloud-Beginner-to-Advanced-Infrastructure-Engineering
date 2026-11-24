hub_project_id       = "meridian-net-hub-3300"
onprem_project_id    = "meridian-onprem-sim-3301"
analytics_project_id = "meridian-analytics-5100"

hub_subnets = {
  core      = "10.200.0.0/24"
  analytics = "10.200.8.0/24" # shared with the analytics service project
}

onprem_subnets = {
  dc = "192.168.10.0/24"
}

# Announced to on-prem so it can reach the spokes through the hub.
spoke_ranges = ["10.10.0.0/16", "10.20.0.0/16"]

spoke_networks = {
  dev  = "projects/meridian-dev-4821/global/networks/meridian-dev-vpc"
  prod = "projects/meridian-prod-7730/global/networks/meridian-prod-vpc"
}

onprem_dns_servers = ["192.168.10.53"]
