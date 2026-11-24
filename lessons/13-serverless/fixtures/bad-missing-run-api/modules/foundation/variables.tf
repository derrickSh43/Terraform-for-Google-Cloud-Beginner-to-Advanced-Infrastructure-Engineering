variable "project_id" {
  description = "Project that owns the environment."
  type        = string
}

variable "region" {
  description = "Region for regional resources (also the bucket location)."
  type        = string
}

variable "labels" {
  description = "Labels applied to every labelled resource in this module."
  type        = map(string)
}

variable "apis" {
  description = "Google Cloud APIs to enable."
  type        = set(string)
  default = [
    "compute.googleapis.com",
    "iam.googleapis.com",
    "storage.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "servicenetworking.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
  ]
}

variable "backup_retention_days" {
  description = "Minimum age before a backup object can be deleted or overwritten."
  type        = number
  default     = 7
}
