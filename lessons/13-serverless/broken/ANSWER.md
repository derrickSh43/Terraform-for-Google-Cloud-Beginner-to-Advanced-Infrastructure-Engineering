# Answer — Troubleshooting 13

**Symptom:** R13.5: `The service is invokable by the whole internet: ['allUsers roles/run.invoker']`.

**Root cause:** two changes together.

1. `ingress = "INGRESS_TRAFFIC_ALL"` made the `https://meridian-catalog-…run.app` URL reachable from anywhere.
2. A `google_cloud_run_v2_service_iam_member` gave `roles/run.invoker` to **`allUsers`**,
   so no authentication is required either. (The broken version also dropped `invoker_iam_disabled`.)

Traffic to the `run.app` URL never touches the load balancer, so Cloud Armor, the
load balancer's logs and its TLS policy simply aren't in the path.

**Fix:** restore

```hcl
ingress              = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
invoker_iam_disabled = true
```

and delete the `allUsers` binding.

**Testing without a public endpoint:** call the load balancer (`https://dev…/api/...`), or use
`gcloud run services proxy meridian-catalog --region us-central1`. The proxy authenticates with the
developer's own identity, which needs `roles/run.invoker` granted to a group on that service, never `allUsers`.

**Which fix matters more:** ingress. With `INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER`, the
`run.app` URL is unreachable from the internet regardless of IAM. IAM is the second layer.
