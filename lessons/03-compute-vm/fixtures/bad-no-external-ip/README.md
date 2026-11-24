Removing `access_config {}` makes `network_interface[0].access_config[0]` in
outputs.tf an invalid index, so `terraform plan` fails before requirement checks run.
