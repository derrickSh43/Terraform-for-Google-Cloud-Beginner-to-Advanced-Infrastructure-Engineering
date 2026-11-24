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

variable "psa_range_address" {
  description = "Start of the /20 reserved for Google-managed services (Cloud SQL)."
  type        = string
}

variable "db_tier" {
  description = "Cloud SQL machine tier."
  type        = string
}

variable "db_availability_type" {
  description = "ZONAL or REGIONAL."
  type        = string
}

variable "db_retained_backups" {
  description = "Daily backups to keep."
  type        = number
}

variable "catalog_image" {
  description = "Catalog API image, pinned by digest."
  type        = string
}

variable "catalog_min_instances" {
  description = "Warm Cloud Run instances for the catalog API."
  type        = number
}

variable "project_number" {
  description = "Numeric project number (Pub/Sub service agent)."
  type        = string
}

variable "order_worker_image" {
  description = "Order worker image, pinned by digest."
  type        = string
}

variable "order_worker_max_instances" {
  description = "Upper bound on order worker instances."
  type        = number
}

variable "secondary_ranges" {
  description = "Secondary ranges per subnet tier (GKE pods and services)."
  type        = map(map(string))
  default     = {}
}

variable "gke_master_cidr" {
  description = "/28 for the GKE private control plane."
  type        = string
}

variable "gke_release_channel" {
  description = "GKE release channel."
  type        = string
}

variable "github_repository" {
  description = "GitHub repository (owner/name) whose workflows may authenticate."
  type        = string
}
