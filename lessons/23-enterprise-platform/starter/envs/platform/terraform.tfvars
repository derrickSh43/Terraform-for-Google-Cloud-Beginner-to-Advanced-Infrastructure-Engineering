org_id          = "123456789012"
billing_account = "01A2B3-C4D5E6-F7A8B9"
seed_project_id = "meridian-ops-1002"

platform_group  = "meridian-platform@meridianbooks.example"
developer_group = "meridian-developers@meridianbooks.example"

projects = {
  "meridian-network" = {
    folder = "shared", env = "shared", cost_center = "cc-9000", owner = "team-platform", budget = 300
    apis   = ["compute.googleapis.com", "dns.googleapis.com"]
  }
  "meridian-logging" = {
    folder = "shared", env = "shared", cost_center = "cc-9000", owner = "team-platform", budget = 200
    apis   = ["logging.googleapis.com"]
  }
  "meridian-shop-dev" = {
    folder = "dev", env = "dev", cost_center = "cc-1001", owner = "team-storefront", budget = 500, shared_vpc = true
    apis   = ["compute.googleapis.com", "run.googleapis.com", "sqladmin.googleapis.com"]
  }
  "meridian-shop-prod" = {
    folder = "prod", env = "prod", cost_center = "cc-1001", owner = "team-storefront", budget = 3000, shared_vpc = true
    apis   = ["compute.googleapis.com", "run.googleapis.com", "sqladmin.googleapis.com"]
  }
}
