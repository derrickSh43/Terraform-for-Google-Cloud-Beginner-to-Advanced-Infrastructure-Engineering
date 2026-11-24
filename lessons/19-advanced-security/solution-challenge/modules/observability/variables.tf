variable "project_id" {
  description = "Project being monitored."
  type        = string
}

variable "environment" {
  description = "Environment name for display names."
  type        = string
}

variable "region" {
  description = "Region for the audit-log bucket."
  type        = string
}

variable "oncall_email" {
  description = "Where alerts go."
  type        = string
}

variable "lb_ip" {
  description = "Public IP of the storefront load balancer (uptime check target)."
  type        = string
}

variable "dead_letter_subscription" {
  description = "Subscription ID that collects dead-lettered order events."
  type        = string
}

variable "worker_service_name" {
  description = "Cloud Run service name of the order worker."
  type        = string
}

variable "audit_retention_days" {
  description = "Minimum age before audit log objects can be deleted."
  type        = number
  default     = 365
}

variable "labels" {
  description = "Labels for created resources."
  type        = map(string)
}

variable "kms_key_id" {
  description = "Cloud KMS key for default encryption (null = Google-managed keys)."
  type        = string
  default     = null
}
