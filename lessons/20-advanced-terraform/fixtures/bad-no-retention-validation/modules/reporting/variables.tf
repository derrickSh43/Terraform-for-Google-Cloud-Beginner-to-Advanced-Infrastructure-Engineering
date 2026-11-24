variable "project_id" {
  description = "Project that owns the reporting resources."
  type        = string
}

variable "name_prefix" {
  description = "Prefix for globally unique names, e.g. meridian-dev."
  type        = string
}

variable "region" {
  description = "Region for the buckets."
  type        = string
}

variable "labels" {
  description = "Labels for every reporting bucket (must match what is deployed, including labels added outside Terraform that we keep)."
  type        = map(string)
}

variable "retention_days" {
  description = "Days a daily report is kept before it's deleted."
  type        = number
  default     = 90
}
