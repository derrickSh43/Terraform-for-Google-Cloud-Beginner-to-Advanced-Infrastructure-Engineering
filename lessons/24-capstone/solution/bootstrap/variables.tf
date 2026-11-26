variable "project_id" {
  description = "Operations project that owns shared infrastructure such as Terraform state."
  type        = string
}

variable "region" {
  description = "Region for the state bucket."
  type        = string
  default     = "us-central1"
}

variable "ci_projects" {
  description = "Environment => project that hosts its CI identities (lesson 16). Their state access is granted here."
  type        = map(string)
  default     = {}
}
