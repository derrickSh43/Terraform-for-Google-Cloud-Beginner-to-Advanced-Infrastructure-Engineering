# The platform's state is the most sensitive of all: it can create and delete
# projects. Its own prefix, and in a real organisation its own bucket and team.
terraform {
  backend "gcs" {
    bucket = "meridian-ops-1002-tfstate"
    prefix = "envs/platform"
  }
}
