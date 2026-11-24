variable "name_prefix" {
  description = "Environment prefix, e.g. meridian-dev."
  type        = string
}

variable "forwarding_rule_name" {
  description = "Name of the external load balancer's forwarding rule."
  type        = string
}

variable "goal" {
  description = "Share of good requests over 28 days."
  type        = number
  default     = 0.995

  validation {
    condition     = var.goal >= 0.9 && var.goal < 1
    error_message = "goal is a fraction below 1 (0.995 = 99.5%). 100% leaves no error budget."
  }
}

variable "notification_channel" {
  description = "Notification channel for SLO alerts."
  type        = string
}
