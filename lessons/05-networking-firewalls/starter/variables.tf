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

variable "web_subnet_cidr" {
  description = "Primary IPv4 range of the web subnet."
  type        = string
  default     = "10.10.1.0/24"
}
