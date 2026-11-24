variable "topic_name" {
  description = "Base name for the topic, subscriptions and push identity (e.g. orders)."
  type        = string
}

variable "project_number" {
  description = "Numeric project number (the Pub/Sub service agent's address contains it)."
  type        = string
}

variable "region" {
  description = "Region for the Cloud Scheduler job."
  type        = string
}

variable "push_endpoint" {
  description = "HTTPS endpoint the subscription pushes to (the worker's Cloud Run URL)."
  type        = string
}

variable "max_delivery_attempts" {
  description = "Deliveries before a message moves to the dead-letter topic (5-100)."
  type        = number
  default     = 5
}

variable "publishers" {
  description = "Principals allowed to publish events to the topic."
  type        = list(string)
  default     = []
}

variable "labels" {
  description = "Labels for topics and subscriptions."
  type        = map(string)
}
