module "hub_apis" {
  source = "../../modules/project-apis"
  apis   = ["compute.googleapis.com", "dns.googleapis.com"]
}

module "onprem_apis" {
  source    = "../../modules/project-apis"
  providers = { google = google.onprem }
  apis      = ["compute.googleapis.com"]
}

module "hub_network" {
  source = "../../modules/network"

  name_prefix = "meridian-hub"
  region      = var.region
  subnets     = var.hub_subnets

  depends_on = [module.hub_apis]
}

# The same network module, deployed into the other project via the alias.
module "onprem_network" {
  source    = "../../modules/network"
  providers = { google = google.onprem }

  name_prefix = "meridian-onprem-sim"
  region      = var.region
  subnets     = var.onprem_subnets

  depends_on = [module.onprem_apis]
}

module "vpn" {
  source = "../../modules/ha-vpn"
  providers = {
    google      = google
    google.peer = google.onprem
  }

  name              = "meridian-hub-onprem"
  region            = var.region
  network_id        = module.hub_network.network_id
  peer_network_id   = module.onprem_network.network_id
  local_asn         = 15169
  peer_asn          = 64515
  advertised_ranges = var.spoke_ranges
}

module "shared_vpc" {
  source = "../../modules/shared-vpc"

  host_project_id = var.hub_project_id
  region          = var.region

  service_projects = {
    (var.analytics_project_id) = {
      subnet_name = "meridian-hub-analytics"
      member      = "group:meridian-analytics@meridianbooks.example"
    }
  }

  depends_on = [module.hub_network]
}

module "dns" {
  source = "../../modules/dns-hybrid"

  network_id         = module.hub_network.network_id
  corp_domain        = "corp.meridianbooks.internal"
  onprem_dns_servers = var.onprem_dns_servers

  depends_on = [module.hub_apis]
}

# Hub side of each hub-and-spoke peering: share the routes learned from on-prem.
module "spoke_peering" {
  source   = "../../modules/peering-half"
  for_each = var.spoke_networks

  name                 = "meridian-hub-to-${each.key}"
  network_id           = module.hub_network.network_id
  peer_network_id      = each.value
  export_custom_routes = true
}
