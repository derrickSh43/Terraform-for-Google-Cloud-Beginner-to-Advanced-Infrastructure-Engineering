variable "name_prefix" {
  description = "Prefix for every load balancer resource name, e.g. meridian-dev."
  type        = string
}

variable "instance_groups" {
  description = "Instance group URLs (e.g. a regional MIG's instance_group) that serve traffic. Each needs a named port \"http\"."
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

variable "api_neg_id" {
  description = "Serverless NEG that serves /api/* (the Cloud Run catalog service)."
  type        = string
}
