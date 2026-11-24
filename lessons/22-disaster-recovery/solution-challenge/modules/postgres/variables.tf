variable "name_prefix" {
  description = "Prefix for resource names, e.g. meridian-dev."
  type        = string
}

variable "region" {
  description = "Region of the instance."
  type        = string
}

variable "network_id" {
  description = "VPC with Private Service Access (pass the private-services module's network_id output)."
  type        = string
}

variable "tier" {
  description = "Machine tier. Shared-core tiers (db-f1-micro, db-g1-small) are for dev only."
  type        = string
  default     = "db-g1-small"
}

variable "availability_type" {
  description = "ZONAL (one zone) or REGIONAL (standby in a second zone, automatic failover)."
  type        = string
  default     = "ZONAL"
}

variable "retained_backups" {
  description = "Number of daily backups to keep."
  type        = number
  default     = 7
}

variable "secret_readers" {
  description = "Principals allowed to read the database password secret, e.g. serviceAccount:app@..."
  type        = list(string)
  default     = []
}

variable "labels" {
  description = "Labels for the instance and secret."
  type        = map(string)
}

variable "dr_region" {
  description = "Region for the cross-region read replica (null = no replica)."
  type        = string
  default     = null

  validation {
    condition     = var.dr_region == null || var.dr_region != var.region
    error_message = "dr_region must differ from region: a replica in the same region doesn't survive a region outage."
  }
}

variable "backup_location" {
  description = "Multi-region for automated backups (e.g. us). null = Google's default."
  type        = string
  default     = null
}
