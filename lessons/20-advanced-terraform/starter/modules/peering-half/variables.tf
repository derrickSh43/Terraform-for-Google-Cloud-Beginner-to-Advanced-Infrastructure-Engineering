variable "name" {
  description = "Peering name."
  type        = string
}

variable "network_id" {
  description = "This side's network."
  type        = string
}

variable "peer_network_id" {
  description = "The other network (full ID: projects/<p>/global/networks/<n>)."
  type        = string
}

variable "import_custom_routes" {
  description = "Learn the peer's custom routes (e.g. on-prem routes from its VPN)."
  type        = bool
  default     = false
}

variable "export_custom_routes" {
  description = "Share this network's custom routes with the peer."
  type        = bool
  default     = false
}
