variable "hub_project_id" {
  description = "Network hub / Shared VPC host project."
  type        = string
}

variable "onprem_project_id" {
  description = "Project that simulates the on-prem data centre."
  type        = string
}

variable "analytics_project_id" {
  description = "Service project attached to the Shared VPC."
  type        = string
}

variable "region" {
  description = "Region for the hub, VPN and on-prem simulation."
  type        = string
  default     = "us-central1"
}

variable "hub_subnets" {
  description = "Hub subnets: tier => CIDR."
  type        = map(string)
}

variable "onprem_subnets" {
  description = "Simulated on-prem subnets: name => CIDR."
  type        = map(string)
}

variable "spoke_ranges" {
  description = "Spoke VPC ranges the hub announces to on-prem over BGP."
  type        = list(string)
}

variable "spoke_networks" {
  description = "Spoke name => full network ID, for the hub side of each peering."
  type        = map(string)
}

variable "onprem_dns_servers" {
  description = "On-prem DNS servers (inside the on-prem range)."
  type        = list(string)
}
