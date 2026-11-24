variable "network_a_id" {
  description = "ID (or self_link) of the first VPC network."
  type        = string
}

variable "network_b_id" {
  description = "ID (or self_link) of the second VPC network."
  type        = string
}

variable "name_a_to_b" {
  description = "Name of the peering created on network A."
  type        = string
}

variable "name_b_to_a" {
  description = "Name of the peering created on network B."
  type        = string
}
