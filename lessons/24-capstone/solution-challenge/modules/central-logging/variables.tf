variable "folder" {
  description = "Folder whose logs (including all children) are collected."
  type        = string
}

variable "logging_project_id" {
  description = "Project that holds the central log bucket."
  type        = string
}

variable "retention_days" {
  description = "How long central logs are kept."
  type        = number
  default     = 400
}
