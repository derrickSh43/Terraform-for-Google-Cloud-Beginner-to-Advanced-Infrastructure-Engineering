variable "name_prefix" {
  description = "Prefix for resource names, e.g. meridian-dev."
  type        = string
}

variable "network_id" {
  description = "VPC network that gets private access to Google-managed services."
  type        = string
}

variable "range_address" {
  description = "First address of the range reserved for managed services (must not overlap any subnet or peer)."
  type        = string
}

variable "range_prefix_length" {
  description = "Size of the reserved range (/20 = 4096 addresses; Google recommends /16 for large estates)."
  type        = number
  default     = 20
}
