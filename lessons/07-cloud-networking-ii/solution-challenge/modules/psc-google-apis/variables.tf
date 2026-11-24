variable "name" {
  description = "Endpoint name: 1-20 characters, lowercase letters and digits only."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9]{0,19}$", var.name))
    error_message = "PSC endpoint names are 1-20 lowercase letters/digits, starting with a letter."
  }
}

variable "network_id" {
  description = "VPC network that gets the endpoint."
  type        = string
}

variable "ip_address" {
  description = "Internal IP for the endpoint. Must not be inside any subnet range."
  type        = string
}
