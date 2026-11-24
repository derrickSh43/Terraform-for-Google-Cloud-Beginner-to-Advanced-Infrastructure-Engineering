variable "name" {
  description = "Prefix for VPN resource names."
  type        = string
}

variable "region" {
  description = "Region of both gateways."
  type        = string
}

variable "network_id" {
  description = "This side's VPC (default provider)."
  type        = string
}

variable "peer_network_id" {
  description = "The other side's VPC (google.peer provider)."
  type        = string
}

variable "local_asn" {
  description = "Private BGP ASN for this side's Cloud Router."
  type        = number
}

variable "peer_asn" {
  description = "Private BGP ASN for the other side."
  type        = number
}

variable "advertised_ranges" {
  description = "Extra CIDRs this side announces (e.g. peered spoke VPCs)."
  type        = list(string)
  default     = []
}

variable "link_ranges" {
  description = "Two link-local /30s (169.254.0.0/16), one per tunnel pair."
  type        = list(string)
  default     = ["169.254.0.0/30", "169.254.0.4/30"]

  validation {
    condition = length(var.link_ranges) == 2 && length(distinct(var.link_ranges)) == 2 && alltrue([
      for r in var.link_ranges : can(regex("^169[.]254[.][0-9]+[.][0-9]+/30$", r))
    ])
    error_message = "link_ranges must be two different /30s inside 169.254.0.0/16."
  }
}
