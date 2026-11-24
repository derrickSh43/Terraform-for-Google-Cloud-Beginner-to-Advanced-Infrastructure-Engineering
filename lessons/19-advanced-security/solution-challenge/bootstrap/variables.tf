variable "project_id" {
  description = "Operations project that owns shared infrastructure such as Terraform state."
  type        = string
}

variable "region" {
  description = "Region for the state bucket."
  type        = string
  default     = "us-central1"
}
