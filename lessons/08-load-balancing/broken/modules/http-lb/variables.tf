variable "name_prefix" {
  description = "Prefix for every load balancer resource name, e.g. meridian-dev."
  type        = string
}

variable "zone" {
  description = "Zone of the backend VMs (an unmanaged instance group is zonal)."
  type        = string
}

variable "instances" {
  description = "Self links of the VMs that serve traffic."
  type        = list(string)
}

variable "port" {
  description = "Port the VMs serve HTTP on (also used for health checks)."
  type        = number
  default     = 80
}

variable "health_check_path" {
  description = "HTTP path the health check requests; must return 200 when the VM is healthy."
  type        = string
  default     = "/"
}
