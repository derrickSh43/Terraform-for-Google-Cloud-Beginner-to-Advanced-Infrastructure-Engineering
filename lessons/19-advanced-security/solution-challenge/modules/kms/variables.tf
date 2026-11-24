variable "environment" {
  description = "Environment name (key ring name suffix)."
  type        = string
}

variable "region" {
  description = "Key location - must match the buckets that use it."
  type        = string
}

variable "project_number" {
  description = "Project number (Cloud Storage service agent address)."
  type        = string
}

variable "rotation_days" {
  description = "Automatic rotation period in days."
  type        = number
  default     = 90

  validation {
    condition     = var.rotation_days >= 1 && var.rotation_days <= 90
    error_message = "Rotate keys at least every 90 days."
  }
}

variable "labels" {
  description = "Labels for the keys."
  type        = map(string)
}
