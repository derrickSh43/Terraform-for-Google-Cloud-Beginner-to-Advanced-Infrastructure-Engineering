# Course-wide provider pins. `python course.py setup` downloads these from the
# Terraform Registry once into a shared plugin cache, and every lesson reuses it.
# The lock file next to this one is copied into any student folder that has no
# lock file, so every learner gets byte-identical provider versions.
terraform {
  required_version = ">= 1.9.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.12"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7"
    }
  }
}
