variable "name_prefix" {
  description = "Prefix for every resource name, e.g. meridian-dev."
  type        = string
}

variable "region" {
  description = "Region for the subnets."
  type        = string
}

variable "subnets" {
  description = "Subnet tier name => primary IPv4 CIDR."
  type        = map(string)
}

variable "enable_nat" {
  description = "Create a Cloud Router and Cloud NAT so private VMs can reach the internet."
  type        = bool
  default     = false
}

variable "secondary_ranges" {
  description = "Secondary ranges per subnet tier: tier => { range_name => CIDR }."
  type        = map(map(string))
  default     = {}
}

variable "routing_mode" {
  description = "REGIONAL or GLOBAL (a hub with VPN routes for several regions needs GLOBAL)."
  type        = string
  default     = "REGIONAL"
}
