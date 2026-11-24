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

variable "nat_subnets" {
  description = "Subnet tier names (keys of var.subnets) that get Cloud NAT. Empty = every subnet."
  type        = set(string)
  default     = []

  validation {
    condition     = alltrue([for s in var.nat_subnets : contains(keys(var.subnets), s)])
    error_message = "Every entry in nat_subnets must be a key of var.subnets."
  }
}

variable "nat_ip_count" {
  description = "Number of reserved external IPs for NAT. 0 = Google-allocated (AUTO_ONLY)."
  type        = number
  default     = 0
}
