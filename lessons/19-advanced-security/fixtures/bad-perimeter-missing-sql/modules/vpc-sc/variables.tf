variable "access_policy_id" {
  description = "Organization access policy ID."
  type        = string
}

variable "name" {
  description = "Perimeter name (letters, digits, underscores)."
  type        = string
}

variable "project_number" {
  description = "Project number placed inside the perimeter."
  type        = string
}

variable "restricted_services" {
  description = "APIs that can't be reached across the perimeter."
  type        = list(string)
  default     = ["storage.googleapis.com", "secretmanager.googleapis.com", "bigquery.googleapis.com"]
}
