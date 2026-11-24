terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
      # The module manages two sides: the default provider (this network) and google.peer (the other one).
      configuration_aliases = [google.peer]
    }
  }
}
