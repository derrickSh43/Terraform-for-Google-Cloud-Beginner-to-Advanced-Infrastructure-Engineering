variable "org_id" {
  description = "Numeric organization ID."
  type        = string
}

variable "billing_account" {
  description = "Billing account for every project."
  type        = string
}

variable "seed_project_id" {
  description = "Project the platform pipeline runs in (API quota, state)."
  type        = string
}

variable "region" {
  description = "Default region."
  type        = string
  default     = "us-central1"
}

variable "platform_group" {
  description = "Platform team group."
  type        = string
}

variable "developer_group" {
  description = "Developers group."
  type        = string
}

variable "projects" {
  description = "Projects the factory creates (see modules/project-factory)."
  type        = any
}

variable "essential_contacts" {
  description = "Notification category => email."
  type        = map(string)
  default     = {}
}
