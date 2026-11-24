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

variable "project_number" {
  description = "Numeric project number (budgets filter by number, not ID)."
  type        = string
}

variable "billing_account" {
  description = "Billing account ID in the form XXXXXX-XXXXXX-XXXXXX."
  type        = string

}

variable "monthly_budget_usd" {
  description = "Monthly spend that triggers budget alerts."
  type        = number
  default     = 25
}
