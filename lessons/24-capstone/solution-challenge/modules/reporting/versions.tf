# A module states the provider range it was written and tested for. The root
# picks the exact version (lock file); the module only rules out the ones it
# can't work with.
terraform {
  required_version = ">= 1.9.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 8.0, < 9.0"
    }
  }
}
