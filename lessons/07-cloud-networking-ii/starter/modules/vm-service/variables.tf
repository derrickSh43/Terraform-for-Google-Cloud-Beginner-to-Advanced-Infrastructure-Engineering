variable "name" {
  description = "Short workload name (web, app). Used for the SA, VM name and network tag."
  type        = string
}

variable "display_name" {
  description = "Human-readable service account name."
  type        = string
}

variable "description" {
  description = "What this workload does."
  type        = string
}

variable "project_id" {
  description = "Project for the IAM grants."
  type        = string
}

variable "zone" {
  description = "Zone for the VM."
  type        = string
}

variable "subnet_id" {
  description = "Subnet the VM attaches to."
  type        = string
}

variable "external_ip" {
  description = "Give the VM an ephemeral public IP."
  type        = bool
  default     = false
}

variable "machine_type" {
  description = "Machine type for the VM."
  type        = string
  default     = "e2-micro"
}

variable "startup_script" {
  description = "Startup script contents (not a path)."
  type        = string
}

variable "roles" {
  description = "Project roles granted to the workload's service account."
  type        = set(string)
  default     = ["roles/logging.logWriter", "roles/monitoring.metricWriter"]
}

variable "labels" {
  description = "Base labels; a role label is added automatically."
  type        = map(string)
}
