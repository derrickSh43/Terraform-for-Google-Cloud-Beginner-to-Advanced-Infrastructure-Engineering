# The environment root only wires modules together. All resources live in
# ../../modules, so dev and prod share exactly the same code.

locals {
  name_prefix = "meridian-${var.environment}"
  labels = {
    app        = "meridian"
    env        = var.environment
    managed_by = "terraform"
  }
}

module "foundation" {
  source = "../../modules/foundation"

  project_id = var.project_id
  region     = var.region
  labels     = local.labels
}

module "network" {
  source = "../../modules/network"

  name_prefix = local.name_prefix
  region      = var.region
  subnets     = var.subnets

  depends_on = [module.foundation]
}

module "firewall" {
  source = "../../modules/firewall"

  name_prefix = local.name_prefix
  network_id  = module.network.network_id

  rules = {
    "allow-http" = {
      description   = "Public HTTP to the web tier."
      source_ranges = ["0.0.0.0/0"]
      target_tags   = ["web"]
      ports         = ["80"]
    }
    "allow-iap-ssh" = {
      description   = "SSH only through Identity-Aware Proxy TCP forwarding."
      source_ranges = ["35.235.240.0/20"]
      target_tags   = ["web", "app"]
      ports         = ["22"]
    }
    "allow-web-to-app" = {
      description = "Web tier calls the API on 8080."
      source_tags = ["web"]
      target_tags = ["app"]
      ports       = ["8080"]
    }
  }
}

module "web" {
  source = "../../modules/vm-service"

  name           = "web"
  display_name   = "Meridian web tier"
  description    = "Runs the Meridian storefront VMs."
  project_id     = var.project_id
  zone           = var.zone
  subnet_id      = module.network.subnet_ids["web"]
  external_ip    = true
  startup_script = file("${path.root}/../../scripts/startup.sh")
  labels         = local.labels

  depends_on = [module.foundation]
}

module "app" {
  source = "../../modules/app-vm"

  name           = "app"
  display_name   = "Meridian app tier"
  description    = "Runs the Meridian API VMs."
  project_id     = var.project_id
  zone           = var.zone
  subnet_id      = module.network.subnet_ids["app"]
  startup_script = file("${path.root}/../../scripts/app-startup.sh")
  labels         = local.labels

  depends_on = [module.foundation]
}
