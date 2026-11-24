variable "billing_account" {
  description = "Billing account every project is charged to."
  type        = string
}

variable "folders" {
  description = "Folder key => folders/<id> (from the landing zone)."
  type        = map(string)
}

variable "shared_vpc_host" {
  description = "Key of the project that hosts the Shared VPC."
  type        = string
}

variable "projects" {
  description = "Project name => settings. Labels are mandatory and validated."
  type = map(object({
    folder      = string
    env         = string
    cost_center = string
    owner       = string
    budget      = number
    apis        = optional(list(string), [])
    shared_vpc  = optional(bool, false)
  }))

  validation {
    condition     = alltrue([for p in values(var.projects) : contains(["dev", "prod", "shared"], p.env)])
    error_message = "env must be dev, prod or shared."
  }

  validation {
    condition     = alltrue([for p in values(var.projects) : length(trimspace(p.owner)) > 0])
    error_message = "Every project needs an owner."
  }

  validation {
    condition     = alltrue([for p in values(var.projects) : p.budget > 0])
    error_message = "Every project needs a budget above zero."
  }
}
