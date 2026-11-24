variable "project_id" {
  description = "Google Cloud project for this environment."
  type        = string
}

variable "region" {
  description = "Default region for regional resources."
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "Zone for VMs. Must be inside var.region."
  type        = string
  default     = "us-central1-a"
}

variable "environment" {
  description = "Environment name: used in resource names and labels."
  type        = string
}

variable "subnets" {
  description = "Subnet tier name => CIDR. Needs \"web\" and \"app\" tiers."
  type        = map(string)
}

variable "ops_subnets" {
  description = "Subnets of the peered operations VPC (name => CIDR). Must not overlap var.subnets."
  type        = map(string)
}

variable "web_zones" {
  description = "Zones for the web tier's managed instance group."
  type        = list(string)
}

variable "web_min_replicas" {
  description = "Minimum web VMs."
  type        = number
}

variable "web_max_replicas" {
  description = "Maximum web VMs."
  type        = number
}

variable "ci_impersonators" {
  description = "Groups allowed to impersonate the CI service account."
  type        = list(string)
}

variable "developer_groups" {
  description = "Group principal => predefined roles for human access."
  type        = map(list(string))
}

variable "backup_retention_days" {
  description = "Retention period for the backups bucket, in days."
  type        = number
}

variable "snapshot_retention_days" {
  description = "How long daily snapshots of the app data disk are kept."
  type        = number
}
