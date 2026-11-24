# State lives in the bucket created by ../../bootstrap, one prefix per environment.
# (The course checker swaps this for local state so plans run offline.)
terraform {
  backend "gcs" {
    bucket = "meridian-ops-1002-tfstate"
    prefix = "envs/prod"
  }
}
