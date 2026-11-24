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

  backup_retention_days = var.backup_retention_days
}

module "network" {
  source = "../../modules/network"

  name_prefix = local.name_prefix
  region      = var.region
  subnets     = var.subnets
  enable_nat  = true # the app tier has no external IP but must install packages

  depends_on = [module.foundation]
}

# A second VPC for operations tooling (monitoring, CI runners), peered to the
# main network. Same module, different inputs.
module "ops_network" {
  source = "../../modules/network"

  name_prefix = "${local.name_prefix}-ops"
  region      = var.region
  subnets     = var.ops_subnets

  depends_on = [module.foundation]
}

module "peering" {
  source = "../../modules/peering"

  network_a_id = module.network.network_id
  network_b_id = module.ops_network.network_id
  name_a_to_b  = "${local.name_prefix}-to-ops"
  name_b_to_a  = "${local.name_prefix}-ops-to-main"
}

module "firewall" {
  source = "../../modules/firewall"

  name_prefix = local.name_prefix
  network_id  = module.network.network_id

  rules = {
    # Only Google's load balancer proxies and health checkers reach the web VMs.
    "allow-google-lb" = {
      description   = "Google Front Ends and health checkers to the web tier."
      source_ranges = ["130.211.0.0/22", "35.191.0.0/16"]
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
    "allow-ops-monitoring" = {
      description   = "Monitoring in the peered ops VPC scrapes node exporter."
      source_ranges = values(var.ops_subnets)
      target_tags   = ["web", "app"]
      ports         = ["9100"]
    }
  }
}

module "web" {
  source = "../../modules/mig-service" # was vm-service: same SA + IAM addresses, VM -> MIG

  name           = "web"
  display_name   = "Meridian web tier"
  description    = "Runs the Meridian storefront VMs."
  project_id     = var.project_id
  region         = var.region
  zones          = var.web_zones
  subnet_id      = module.network.subnet_ids["web"]
  startup_script = file("${path.root}/../../scripts/startup.sh")
  labels         = local.labels

  min_replicas = var.web_min_replicas
  max_replicas = var.web_max_replicas

  depends_on = [module.foundation]
}

module "app" {
  source = "../../modules/vm-service"

  name           = "app"
  display_name   = "Meridian app tier"
  description    = "Runs the Meridian API VMs."
  project_id     = var.project_id
  zone           = var.zone
  subnet_id      = module.network.subnet_ids["app"]
  startup_script = file("${path.root}/../../scripts/app-startup.sh")
  labels         = local.labels

  roles = ["roles/logging.logWriter", "roles/monitoring.metricWriter", "roles/cloudsql.client"]

  data_disk_size_gb       = 20
  snapshot_retention_days = var.snapshot_retention_days
  writable_buckets        = [module.foundation.backups_bucket]

  depends_on = [module.foundation]
}

module "lb" {
  source = "../../modules/http-lb"

  name_prefix     = local.name_prefix
  instance_groups = [module.web.instance_group]
}

module "ci" {
  source = "../../modules/ci-identity"

  project_id    = var.project_id
  assets_bucket = module.foundation.bucket_name
  impersonators = var.ci_impersonators

  depends_on = [module.foundation]
}

module "access" {
  source = "../../modules/project-access"

  project_id  = var.project_id
  group_roles = var.developer_groups
}

module "private_services" {
  source = "../../modules/private-services"

  name_prefix   = local.name_prefix
  network_id    = module.network.network_id
  range_address = var.psa_range_address

  depends_on = [module.foundation]
}

module "db" {
  source = "../../modules/postgres"

  name_prefix       = local.name_prefix
  region            = var.region
  network_id        = module.private_services.network_id
  tier              = var.db_tier
  availability_type = var.db_availability_type
  retained_backups  = var.db_retained_backups
  secret_readers    = ["serviceAccount:${module.app.service_account_email}"]

  iam_service_accounts = [module.app.service_account_email]
  labels               = local.labels
}
