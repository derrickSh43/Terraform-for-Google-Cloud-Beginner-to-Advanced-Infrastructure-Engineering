variable "host_project_id" {
  description = "Project that owns the shared network."
  type        = string
}

variable "region" {
  description = "Region of the shared subnets."
  type        = string
}

variable "service_projects" {
  description = "Service project ID => { subnet_name, member } allowed to use that subnet."
  type = map(object({
    subnet_name = string
    member      = string
  }))
}
