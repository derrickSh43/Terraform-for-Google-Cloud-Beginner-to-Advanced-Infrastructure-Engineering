variable "project_id" {
  description = "Project to grant access in."
  type        = string
}

variable "group_roles" {
  description = "Map of group principal (group:name@domain) => list of predefined roles."
  type        = map(list(string))

  validation {
    condition     = alltrue([for p in keys(var.group_roles) : startswith(p, "group:")])
    error_message = "Grant human access to groups only (keys must start with \"group:\")."
  }

  validation {
    condition = alltrue(flatten([for roles in values(var.group_roles) : [
      for r in roles : !contains(["roles/owner", "roles/editor", "roles/viewer"], r)
    ]]))
    error_message = "Basic roles (owner/editor/viewer) are not allowed: use predefined roles."
  }
}

variable "expires" {
  description = "RFC 3339 timestamp after which all grants stop working (empty = permanent)."
  type        = string
  default     = ""
}
