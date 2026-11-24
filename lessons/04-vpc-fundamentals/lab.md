# Lesson 04 Lab — Meridian's own network

```powershell
python course.py start 04
python course.py check 04
```

The starter is the lesson 03 solution plus an empty `network.tf`.

---

## Step 1 — The VPC (R4.1, R4.2)

In `network.tf`:

- `google_compute_network` with `name = "meridian-${var.environment}-vpc"`
- `auto_create_subnetworks = false` (custom mode)
- `routing_mode = "REGIONAL"`
- `depends_on = [google_project_service.apis]`

## Step 2 — The web subnet

Add `variable "web_subnet_cidr"` (default `"10.10.1.0/24"`), then a
`google_compute_subnetwork`:

- `network = google_compute_network.<your name>.id`
- `region = var.region`
- `ip_cidr_range = var.web_subnet_cidr`
- `private_ip_google_access = true`

Nothing checks this yet: R4.3 – R4.5 find the web subnet through the VM, which moves into it in Step 3.

## Step 3 — Move the VM (R4.3 – R4.6)

In `compute.tf`, replace `network = "default"` with
`subnetwork = google_compute_subnetwork.<your name>.id`. Keep `access_config {}`.

Run the check, then open the plan JSON. On a real project that already had the
lesson 03 VM, what would this change do to it? (See "Moving a VM" in the README.)

## Step 4 — Outputs (R4.7)

`vpc_id` and `web_subnet_id`.

## Reflection questions

1. Your VPC is global, but you chose a region for the subnet. Where would a VM in `europe-west1` go?
2. Why might `10.128.0.0/9` (auto mode) be a problem the day Meridian connects to its office network?
3. Delete `private_ip_google_access` and imagine the VM had no external IP. What breaks first?
