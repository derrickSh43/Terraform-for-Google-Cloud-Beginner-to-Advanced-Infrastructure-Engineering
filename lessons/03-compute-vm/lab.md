# Lesson 03 Lab — The Meridian web server

```powershell
python course.py start 03
python course.py check 03
```

The starter is the lesson 02 solution plus `compute.tf` (empty) and
`scripts/startup.sh` (ready to use: installs NGINX and writes a home page).

---

## Step 1 — A zone variable

Add `variable "zone"` (string, default `"us-central1-a"`, with a description).
A zone is a region plus a letter. Getting this wrong is one of the most common
first-week mistakes.

Nothing checks this yet: R3.2 checks the zone once the VM uses it in Step 2.

## Step 2 — The VM (R3.1, R3.2, R3.3, R3.6)

In `compute.tf`, create the VM as `resource "google_compute_instance" "web"`. The block name matters:
R3.1 checks it, and the challenge test refers to `google_compute_instance.web`.

- `name = "meridian-web-1"`, `machine_type = "e2-micro"`, `zone = var.zone`
- `tags = ["web"]` and the same standard labels as your bucket in `main.tf`, plus a role:

  ```hcl
  labels = {
    app        = "meridian"
    env        = var.environment
    managed_by = "terraform"
    role       = "web"
  }
  ```

  Tags and labels look alike but do different jobs: **network tags** are what firewall rules
  target (lesson 05); **labels** are key/value metadata for billing reports and filtering.
- `boot_disk` → `initialize_params` with image `debian-cloud/debian-12`, `size = 10`, `type = "pd-balanced"`
- `network_interface { network = "default" }`. Every VM needs at least one, or `validate` fails.
  Step 3 gives it a public IP.

Docs: <https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_instance>

## Step 3 — Network and external IP (R3.7)

Add an `access_config` to the `network_interface` from Step 2:

```hcl
network_interface {
  network = "default"
  access_config {}      # empty block = "give me an ephemeral public IP"
}
```

Add outputs `web_external_ip`
(`google_compute_instance.web.network_interface[0].access_config[0].nat_ip`) and
`web_url` (`"http://${...}"`).

## Step 4 — Bootstrap NGINX (R3.4)

```hcl
metadata_startup_script = file("${path.module}/scripts/startup.sh")
```

## Step 5 — Identity and hardening (R3.5, R3.8, R3.9)

- `service_account` block: `email = google_service_account.web.email`, `scopes = ["cloud-platform"]`
- `shielded_instance_config` with all three features set to `true`
- `metadata = { enable-oslogin = "TRUE" }`

## Step 6 — Ordering (R3.10)

The VM references the service account's email, so Terraform already orders
those two. But nothing references the **Compute API** or the **IAM grants**.
Add:

```hcl
depends_on = [
  google_project_service.apis,
  google_project_iam_member.web,
]
```

## Read the plan

Open `.course/build/03l/plan.json` and find the VM. Which
attributes show `true` in `after_unknown`? Those are values only Google knows
after creation, such as the IP address and instance ID.

## Reflection questions

1. Why is the external IP "known after apply" but the zone is not?
2. What would break if the VM booted *before* `roles/logging.logWriter` was granted?
3. Why not just give the VM the default compute service account? (Look up what role it gets by default.)
