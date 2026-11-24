variable "name_prefix" {
  description = "Prefix for every resource name, e.g. meridian-dev."
  type        = string
}

variable "region" {
  description = "Region for the subnets."
  type        = string
}

variable "subnets" {
  description = "Subnet tier name => primary IPv4 CIDR."
  type        = map(string)
}
