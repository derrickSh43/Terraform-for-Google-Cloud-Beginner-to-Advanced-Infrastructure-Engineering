variable "network_id" {
  description = "Network that uses the forwarding zone and gets the inbound forwarder."
  type        = string
}

variable "corp_domain" {
  description = "On-prem DNS domain (without trailing dot)."
  type        = string
}

variable "onprem_dns_servers" {
  description = "On-prem DNS server IPs."
  type        = list(string)
}
