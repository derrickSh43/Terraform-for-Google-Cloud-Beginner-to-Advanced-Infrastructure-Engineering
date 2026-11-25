# Lesson 15 Challenge — Cluster supply chain and costs

```powershell
python course.py check 15 --challenge
```

| ID | Requirement |
|---|---|
| C15.1 | **Only approved images run.** Enforce the project's Binary Authorization policy on the cluster (`evaluation_mode = "PROJECT_SINGLETON_POLICY_ENFORCE"`). Lesson 19 writes the policy itself. |
| C15.2 | **Know what's vulnerable.** Turn on GKE security posture with basic workload vulnerability scanning. |
| C15.3 | **Attribute costs.** Enable GKE cost allocation (`cost_management_config`) and keep resource labels on the cluster. |
| C15.4 | **The module refuses public API access.** Validate `var.authorized_networks`: every entry must be a valid **private** (RFC 1918) CIDR. `tests/challenge/gke_module.tftest.hcl` tries `0.0.0.0/0` and a public office range. Hint: Terraform has no `cidrcontains`, but a regex on the first octets works. |

## Contract for the lesson test

The test calls the module on its own with the lab's eight required inputs, so every other variable needs a default. It looks for
`google_container_cluster.this`.

## Think about it

- With Binary Authorization enforced and no policy written yet, what is the project's default policy, and what would happen to deployments?
- `enable_private_endpoint` can't be changed on an existing cluster without recreating it. Why does that make getting it right on day one so important?
