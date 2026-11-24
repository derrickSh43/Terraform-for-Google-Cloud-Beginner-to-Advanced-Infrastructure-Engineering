variable "name" {
  description = "Service name suffix (catalog -> meridian-catalog)."
  type        = string
}

variable "region" {
  description = "Region of the service."
  type        = string
}

variable "image" {
  description = "Container image, pinned by digest (...@sha256:...)."
  type        = string
}

variable "network_id" {
  description = "VPC for Direct VPC egress."
  type        = string
}

variable "subnet_id" {
  description = "Subnet that provides Direct VPC egress IPs."
  type        = string
}

variable "min_instances" {
  description = "Instances kept warm (0 = scale to zero)."
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Upper bound on instances (cost and database-connection guard rail)."
  type        = number
  default     = 5
}

variable "env" {
  description = "Plain environment variables."
  type        = map(string)
  default     = {}
}

variable "secret_env" {
  description = "Environment variables read from Secret Manager: NAME => secret id."
  type        = map(string)
  default     = {}
}

variable "deletion_protection" {
  description = "Block terraform destroy of the service."
  type        = bool
  default     = true
}

variable "labels" {
  description = "Labels for the service."
  type        = map(string)
}

variable "ingress" {
  description = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER (behind the LB) or INGRESS_TRAFFIC_INTERNAL_ONLY (workers)."
  type        = string
  default     = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
}

variable "create_neg" {
  description = "Create a serverless NEG so a load balancer can route to the service."
  type        = bool
  default     = true
}

variable "invokers" {
  description = "Principals granted roles/run.invoker on this service (keeps per-request IAM on)."
  type        = list(string)
  default     = []
}
