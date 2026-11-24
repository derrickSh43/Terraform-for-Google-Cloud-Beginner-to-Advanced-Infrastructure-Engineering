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
