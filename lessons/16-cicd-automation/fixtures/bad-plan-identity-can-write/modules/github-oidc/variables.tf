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
    "roles/compute.instanceAdmin.v1",
  ]
}

variable "apply_roles" {
  description = "Roles the apply identity needs to manage this platform: one admin role per service, never Owner or Editor."
  type        = list(string)
  default = [
    "roles/compute.admin",
    "roles/storage.admin",
    "roles/iam.serviceAccountAdmin",
    "roles/iam.serviceAccountUser",
    "roles/iam.roleAdmin",
    "roles/iam.workloadIdentityPoolAdmin",
    "roles/resourcemanager.projectIamAdmin",
    "roles/serviceusage.serviceUsageAdmin",
    "roles/servicenetworking.networksAdmin",
    "roles/cloudsql.admin",
    "roles/secretmanager.admin",
    "roles/run.admin",
    "roles/pubsub.admin",
    "roles/cloudscheduler.admin",
    "roles/container.admin",
    "roles/artifactregistry.admin",
    "roles/monitoring.admin",
    "roles/logging.admin",
    "roles/cloudkms.admin",
    "roles/dns.admin",
  ]

  validation {
    condition     = length(setintersection(var.apply_roles, ["roles/owner", "roles/editor"])) == 0
    error_message = "Grant the apply identity specific admin roles, not roles/owner or roles/editor."
  }
}
