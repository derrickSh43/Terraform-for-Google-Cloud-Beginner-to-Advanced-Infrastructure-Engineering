variable "name_prefix" {
  description = "Prefix for rule names, e.g. meridian-dev."
  type        = string
}

variable "network_id" {
  description = "VPC network the rules belong to."
  type        = string
}

variable "rules" {
  description = "Ingress allow rules keyed by short name (the key becomes part of the rule name)."
  type = map(object({
    description   = string
    priority      = optional(number, 1000)
    source_ranges = optional(list(string))
    source_tags   = optional(list(string))
    target_tags   = list(string)
    protocol      = optional(string, "tcp")
    ports         = list(string)
  }))
}
