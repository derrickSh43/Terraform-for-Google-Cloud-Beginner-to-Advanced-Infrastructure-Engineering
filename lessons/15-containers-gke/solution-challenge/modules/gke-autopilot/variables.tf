variable "name" {
  description = "Cluster name (also the prefix of its node service account)."
  type        = string
}

variable "project_id" {
  description = "Project of the cluster (Workload Identity pool <project>.svc.id.goog)."
  type        = string
}

variable "region" {
  description = "Region of the regional cluster."
  type        = string
}

variable "network_id" {
  description = "VPC of the cluster."
  type        = string
}

variable "subnet_id" {
  description = "Subnet for nodes; it must carry the pods and services secondary ranges."
  type        = string
}

variable "pods_range_name" {
  description = "Secondary range name for pod IPs."
  type        = string
  default     = "pods"
}

variable "services_range_name" {
  description = "Secondary range name for Service IPs."
  type        = string
  default     = "services"
}

variable "master_cidr" {
  description = "/28 for the private control plane endpoint (must not overlap anything)."
  type        = string
}

variable "authorized_networks" {
  description = "Private CIDRs allowed to reach the Kubernetes API: display name => CIDR."
  type        = map(string)

  validation {
    condition = alltrue([for c in values(var.authorized_networks) :
      can(cidrnetmask(c)) && can(regex("^(10[.]|192[.]168[.]|172[.](1[6-9]|2[0-9]|3[01])[.])", c))
    ])
    error_message = "Authorized networks must be private (RFC 1918) CIDRs - never 0.0.0.0/0 or public ranges."
  }
}

variable "release_channel" {
  description = "RAPID, REGULAR or STABLE."
  type        = string
  default     = "REGULAR"
}

variable "workloads" {
  description = "Workload Identity bindings: Google SA name suffix => \"namespace/ksa\"."
  type        = map(string)
  default     = {}
}

variable "labels" {
  description = "Labels for the cluster."
  type        = map(string)
}
