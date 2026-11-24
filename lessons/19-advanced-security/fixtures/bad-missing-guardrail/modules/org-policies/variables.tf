variable "project_id" {
  description = "Project the policies apply to."
  type        = string
}

variable "boolean_constraints" {
  description = "Boolean constraints to enforce."
  type        = list(string)
  default = [
    "storage.uniformBucketLevelAccess",
    "storage.publicAccessPrevention",
    "iam.disableServiceAccountKeyCreation",
  ]
}
