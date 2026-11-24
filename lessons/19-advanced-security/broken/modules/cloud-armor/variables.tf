variable "name" {
  description = "Security policy name."
  type        = string
}

variable "requests_per_minute" {
  description = "Requests per minute allowed per client IP before 429s."
  type        = number
  default     = 600
}
