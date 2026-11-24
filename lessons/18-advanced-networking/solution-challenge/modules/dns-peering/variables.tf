variable "name" {
  description = "Zone name."
  type        = string
}

variable "domain" {
  description = "Domain to resolve through the target network."
  type        = string
}

variable "network_id" {
  description = "Network whose queries are peered."
  type        = string
}

variable "target_network_id" {
  description = "Network that resolves them (the hub)."
  type        = string
}
