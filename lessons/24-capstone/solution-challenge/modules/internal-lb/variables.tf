variable "name" {
  description = "Name prefix for the load balancer resources."
  type        = string
}

variable "region" {
  description = "Region of the load balancer and its backends."
  type        = string
}

variable "network_id" {
  description = "VPC of the internal address."
  type        = string
}

variable "subnet_id" {
  description = "Subnet the internal address is taken from."
  type        = string
}

variable "instance_group" {
  description = "Instance group URL of the regional MIG behind the load balancer."
  type        = string
}

variable "port" {
  description = "TCP port the backends listen on."
  type        = number
}

variable "health_check_path" {
  description = "HTTP path the health check requests."
  type        = string
  default     = "/health.json"
}
