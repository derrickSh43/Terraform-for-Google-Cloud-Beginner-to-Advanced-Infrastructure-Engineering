variable "project_id" {
  description = "Google Cloud project ID that will own every Meridian resource."
  type        = string
}

variable "region" {
  description = "Default region for regional resources."
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Deployment environment name, used in labels."
  type        = string
  default     = "dev"
}

variable "zone" {
  description = "Zone for zonal resources such as VMs. Must be inside var.region."
  type        = string
  default     = "us-central1-a"
}

variable "machine_type" {
  description = "Machine type for the web VM. Restricted to small shared-core types to control cost."
  type        = string
  default     = "e2-micro"

  validation {
    condition     = contains(["e2-micro", "e2-small", "e2-medium"], var.machine_type)
    error_message = "machine_type must be one of e2-micro, e2-small or e2-medium."
  }
}
