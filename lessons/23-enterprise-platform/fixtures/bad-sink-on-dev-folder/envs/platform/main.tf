# The landing zone: everything a new team needs before writing its first resource.

module "landing_zone" {
  source = "../../modules/landing-zone"

  org_id          = var.org_id
  platform_group  = var.platform_group
  developer_group = var.developer_group
}

module "projects" {
  source = "../../modules/project-factory"

  billing_account = var.billing_account
  folders         = module.landing_zone.env_folders
  shared_vpc_host = "meridian-network"
  projects        = var.projects
}

module "central_logging" {
  source = "../../modules/central-logging"

  folder             = module.landing_zone.env_folders["dev"]
  logging_project_id = module.projects.project_ids["meridian-logging"]
}
