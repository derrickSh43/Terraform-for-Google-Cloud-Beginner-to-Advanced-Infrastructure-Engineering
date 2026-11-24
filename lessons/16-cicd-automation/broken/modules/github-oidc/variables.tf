variable "project_id" {
  description = "Project that hosts the pool and the CI identities."
  type        = string
}

variable "repository" {
  description = "GitHub repository (owner/name) allowed to authenticate."
  type        = string
}

variable "pool_id" {
  description = "Workload identity pool ID (4-32 characters)."
  type        = string
  default     = "meridian-github"
}

variable "apply_service_account_email" {
  description = "Service account that applies changes (the lesson 10 CI identity)."
  type        = string
}

variable "plan_roles" {
  description = "Read-only roles for the plan identity."
  type        = list(string)
  default = [
    "roles/compute.viewer",
    "roles/iam.securityReviewer",
    "roles/cloudsql.viewer",
    "roles/run.viewer",
    "roles/pubsub.viewer",
    "roles/container.viewer",
    "roles/secretmanager.viewer",
    "roles/serviceusage.serviceUsageViewer",
    "roles/artifactregistry.reader",
  ]
}
