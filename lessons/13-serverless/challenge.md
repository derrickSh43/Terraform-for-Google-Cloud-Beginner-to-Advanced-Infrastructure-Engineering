# Lesson 13 Challenge — Safe serverless releases

```powershell
python course.py check 13 --challenge
```

| ID | Requirement |
|---|---|
| C13.1 | **Canary in prod.** Add `stable_revision` and `canary_percent` variables to the Cloud Run module. When `stable_revision` is set, a `TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION` target keeps `100 - canary_percent`% on that revision and `LATEST` gets the rest. prod: revision `meridian-catalog-00041-abc`, 10% canary. dev: 100% latest. |
| C13.2 | **Health probes.** A `startup_probe` (traffic waits until the app is up) and a `liveness_probe` (hung containers restart), both on `/healthz`. Turn on `startup_cpu_boost`. |
| C13.3 | **Release images are forever.** Add a `KEEP` cleanup policy for tagged images with prefix `release-`. |
| C13.4 | **The module refuses tags and foreign registries.** Validate `var.image` against `^<region>-docker.pkg.dev/...@sha256:<64 hex>$`. `tests/challenge/cloud_run_module.tftest.hcl` tries `:latest` and Docker Hub. |

## Contract for the lesson test

The test calls the module on its own with the lab's six required inputs, so every other variable needs a default. It looks for
`google_cloud_run_v2_service.this`.

## Think about it

- The canary gets 10% of traffic. What has to be true about the database schema while two revisions run side by side?
- Why must the KEEP-release policy exist *before* a DELETE policy could match old release images?
