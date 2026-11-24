project_id  = "meridian-prod-7730"
environment = "prod"

# 10.10.0.0/16 never overlaps dev (10.10.0.0/16), so the two can be peered later.
subnets = {
  web = "10.10.1.0/24"
  app = "10.10.2.0/24"
}
