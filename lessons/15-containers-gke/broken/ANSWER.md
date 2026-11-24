# Answer — Troubleshooting 15

**Symptom:** R15.4: `Authorized networks include public ranges ['0.0.0.0/0']`
(and `enable_private_endpoint = false`).

**Root cause:** the control plane got a public endpoint, and `0.0.0.0/0` was added to
`master_authorized_networks_config`. The Kubernetes API server is now reachable from
anywhere on the internet.

**Why authentication isn't enough:** the API server becomes a target for every future
Kubernetes or GKE vulnerability, any RBAC mistake that grants
`system:anonymous` or `system:authenticated` more than it should, and stolen or
phished kubeconfigs, which now work from anywhere. Network restriction is a layer that
holds even when another one fails.

**Fix:** restore `enable_private_endpoint = true` and remove the `0.0.0.0/0` block. Only
the ops range stays authorized.

**Supported access for humans:** connect from the ops VPC through IAP-tunnelled SSH to
a small tools VM (lessons 05 and 07). Or use **Connect gateway** / DNS-based endpoint
access, which authenticates every request with IAM and needs no network path at all.

**Can Terraform flip it back?** On a deployed cluster, changing
`enable_private_endpoint` forces the cluster to be **replaced**, and
`deletion_protection = true` blocks that. Network-shape decisions on GKE are close to
permanent. That's why R15.4 checks them before the first apply.
