# Lesson 03 — Creating a Basic Compute VM

**Phase 1 · Beginner** · Builds on lesson 02

> Meridian's storefront goes live, as a single NGINX VM for now.
> It runs as the service account you built in lesson 02.

## Learning objectives

- Choose machine types, images and boot disks with cost in mind.
- Bootstrap a VM with a startup script, using `file()` and `templatefile()`.
- Attach a dedicated service account and explain scopes vs. IAM roles.
- Harden a VM: Shielded VM, OS Login, no project-wide SSH keys.
- Use `depends_on` for ordering that Terraform can't infer.

## 1. Concepts

### Anatomy of `google_compute_instance`

| Part | Purpose |
|---|---|
| `machine_type` | vCPU and memory. `e2-micro` (2 shared vCPU, 1 GB) is tiny and cheap. |
| `zone` | VMs are **zonal**. The zone must be inside your region (`us-central1-a`). |
| `boot_disk.initialize_params` | Image (`debian-cloud/debian-12`), size, disk type |
| `network_interface` | Which VPC or subnet. `access_config {}` adds an external IP. |
| `metadata` / `metadata_startup_script` | Key/value pairs the guest reads. The startup script runs as root at boot. |
| `service_account` | The identity the VM's software uses to call Google APIs |
| `shielded_instance_config` | Secure Boot, vTPM and integrity monitoring protect against boot-level malware |

### Scopes vs. IAM roles

Scopes are a legacy, coarse filter on a VM's access tokens. Current guidance:
set `scopes = ["cloud-platform"]` and control access with **IAM roles on a
dedicated service account**. That account is the one from lesson 02, which can
only write logs and metrics.

### SSH: OS Login

`enable-oslogin = "TRUE"` makes SSH access an IAM decision
(`roles/compute.osLogin`), so nobody copies keys onto servers.
`block-project-ssh-keys` stops old project-wide keys from working.

### `file()` vs `templatefile()`

- `file(path)` reads a file as-is.
- `templatefile(path, vars)` renders `${...}` placeholders at **plan time**, so the
  rendered script appears in the plan and the checker can read it.

`path.module` is the folder containing the current `.tf` file. Always build paths from it.

### Conditional expressions

Terraform has no `if` statement. It has one conditional *expression*:

```hcl
condition ? value_if_true : value_if_false
```

```hcl
provisioning_model = var.environment == "prod" ? "STANDARD" : "SPOT"
```

- Both results must be the same type (two strings, two numbers, two lists).
- It picks a **value**. To make a whole resource optional, use it in `count`:
  `count = var.enable_nat ? 1 : 0` (lesson 07). For an optional nested block, use it in
  `dynamic`: `for_each = var.external_ip ? [1] : []` (lesson 06).
- Keep it readable: when you find yourself nesting `? :` inside `? :`, use a map lookup
  instead, such as `local.sizes[var.environment]`.

**Validation vs. conditionals:** a `validation` block (lesson 02) *rejects* values you don't
accept. A conditional *chooses* between values you do accept. Validate `environment` to be
`dev` or `prod`, then branch on it.

## 2. Architecture

```mermaid
flowchart LR
  U((Internet)) -->|"HTTP :80<br/>(firewall: lesson 5)"| VM
  subgraph project["GCP project"]
    subgraph default["default VPC · us-central1-a"]
      VM["meridian-web-1<br/>e2-micro · Debian 12 · NGINX<br/>tag: web"]
    end
    SA["meridian-web<br/>service account"] -. runs as .- VM
    VM -->|logs, metrics| OPS["Cloud Logging / Monitoring"]
  end
```

> For now the VM uses the `default` network. Lesson 4 replaces it with a custom
> VPC, and lesson 5 adds the firewall rules that decide who can reach port 80.

## 3. Lab files

- [lab.md](lab.md): R3.1 – R3.10
- [challenge.md](challenge.md): C3.1 – C3.4, including a native test for variable validation
- [broken/](broken/): *the plan succeeds, so why does the check fail?*

## 4. If this were real

An `e2-micro` in `us-central1` falls under the Compute Engine free tier, one per
billing account. An ephemeral external IPv4 address costs a few dollars a month.
Run `terraform destroy` when you're done.
