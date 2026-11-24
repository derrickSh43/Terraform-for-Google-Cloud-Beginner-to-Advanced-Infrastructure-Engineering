variable "name" {
  description = "Short workload name (web). Used for the SA, template, MIG and network tag."
  type        = string
}

variable "display_name" {
  description = "Human-readable service account name."
  type        = string
}

variable "description" {
  description = "What this workload does."
  type        = string
}

variable "project_id" {
  description = "Project for the IAM grants."
  type        = string
}

variable "region" {
  description = "Region of the managed instance group."
  type        = string
}

variable "zones" {
  description = "Zones the MIG spreads VMs across (at least two)."
  type        = list(string)
}

variable "subnet_id" {
  description = "Subnet the VMs attach to."
  type        = string
}

variable "machine_type" {
  description = "Machine type for every VM."
  type        = string
  default     = "e2-micro"
}

variable "startup_script" {
  description = "Startup script contents (not a path)."
  type        = string
}

variable "roles" {
  description = "Project roles granted to the workload's service account."
  type        = set(string)
  default     = ["roles/logging.logWriter", "roles/monitoring.metricWriter"]
}

variable "labels" {
  description = "Base labels; a role label is added automatically."
  type        = map(string)
}

variable "port" {
  description = "Port the VMs serve HTTP on (named port \"http\")."
  type        = number
  default     = 80
}

variable "health_check_path" {
  description = "Path probed by the autohealing health check."
  type        = string
  default     = "/"
}

variable "autoheal_initial_delay_sec" {
  description = "Grace period after a VM starts before autohealing may recreate it. Must cover boot + startup script."
  type        = number
  default     = 180
}

variable "min_replicas" {
  description = "Minimum number of VMs (keep >= 2 so a single failure isn't an outage)."
  type        = number
  default     = 2
}

variable "max_replicas" {
  description = "Maximum number of VMs the autoscaler may create."
  type        = number
  default     = 4

}

variable "business_hours_min_replicas" {
  description = "Minimum VMs during weekday business hours (0 = no schedule)."
  type        = number
  default     = 0
}

variable "cpu_target" {
  description = "Average CPU utilization the autoscaler aims for (0-1)."
  type        = number
  default     = 0.6
}
