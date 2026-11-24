variable "project_id" {
  description = "Project for the custom role and project-level grant."
  type        = string
}

variable "account_id" {
  description = "Service account ID for the CI identity."
  type        = string
  default     = "meridian-ci"
}

variable "display_name" {
  description = "Human-readable name of the CI service account."
  type        = string
  default     = "CI pipeline"
}

variable "role_id" {
  description = "ID of the custom deployer role (letters, digits, underscores, periods)."
  type        = string
  default     = "meridianCiDeployer"
}

variable "permissions" {
  description = "Exact permissions CI needs. Keep this list short and specific."
  type        = list(string)
  default = [
    "compute.instanceGroupManagers.get",
    "compute.instanceGroupManagers.update",
    "compute.instanceTemplates.get",
    "compute.instanceTemplates.list",
    "compute.instanceTemplates.useReadOnly",
    "compute.instances.list",
    "compute.regionOperations.get",
    "compute.instances.*",
  ]
}

variable "assets_bucket" {
  description = "Name of the static assets bucket CI publishes to."
  type        = string
}

variable "impersonators" {
  description = "Principals (preferably groups) allowed to impersonate the CI account, e.g. group:platform@example.com."
  type        = list(string)
  default     = []
}
