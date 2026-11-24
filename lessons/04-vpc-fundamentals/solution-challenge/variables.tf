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

variable "subnets" {
  description = "Subnet tier name => primary IPv4 CIDR. Must include \"web\"."
  type        = map(string)
  default = {
    web = "10.10.1.0/24"
    app = "10.10.2.0/24"
  }

  validation {
    condition     = alltrue([for cidr in values(var.subnets) : can(cidrnetmask(cidr))])
    error_message = "Every subnet value must be a valid IPv4 CIDR such as 10.10.1.0/24."
  }

  validation {
    condition     = contains(keys(var.subnets), "web")
    error_message = "var.subnets must contain a \"web\" tier."
  }
}
