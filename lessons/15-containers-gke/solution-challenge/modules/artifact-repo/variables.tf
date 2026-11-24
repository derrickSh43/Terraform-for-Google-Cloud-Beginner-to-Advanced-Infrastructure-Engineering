variable "repository_id" {
  description = "Repository name, e.g. meridian."
  type        = string
  default     = "meridian"
}

variable "region" {
  description = "Region of the repository (keep images next to where they run)."
  type        = string
}

variable "writers" {
  description = "Principals allowed to push images (CI)."
  type        = list(string)
  default     = []
}

variable "labels" {
  description = "Labels for the repository."
  type        = map(string)
}

variable "readers" {
  description = "Principals allowed to pull images."
  type        = list(string)
  default     = []
}
