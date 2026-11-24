variable "org_id" {
  description = "Numeric organization ID."
  type        = string
}

variable "environments" {
  description = "Folders created under the Meridian folder."
  type        = list(string)
  default     = ["dev", "prod", "shared"]
}

variable "boolean_constraints" {
  description = "Boolean organization policy constraints enforced on the Meridian folder."
  type        = list(string)
  default = [
    "compute.skipDefaultNetworkCreation",
    "iam.disableServiceAccountKeyCreation",
    "storage.uniformBucketLevelAccess",
  ]
}

variable "platform_group" {
  description = "Group that administers the Meridian folder."
  type        = string
}

variable "developer_group" {
  description = "Group of application developers."
  type        = string
}

variable "developer_roles" {
  description = "Roles developers get on the dev folder (and nowhere else)."
  type        = list(string)
  default     = ["roles/viewer", "roles/logging.viewer"]
}

variable "essential_contacts" {
  description = "Notification category => email (SECURITY, BILLING, TECHNICAL, LEGAL...)."
  type        = map(string)
  default     = {}
}
