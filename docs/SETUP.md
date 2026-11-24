# Setup

## 1. Install the tools

| Tool | Version | Install |
|---|---|---|
| Terraform | ≥ 1.9 | Windows: `winget install Hashicorp.Terraform` · macOS: `brew tap hashicorp/tap && brew install hashicorp/tap/terraform` · Linux: <https://developer.hashicorp.com/terraform/install> |
| Python | ≥ 3.10 | <https://www.python.org/downloads/> (standard library only, no `pip install`) |
| tflint | optional | <https://github.com/terraform-linters/tflint>. Adds a lint stage when present. |
| Editor | any | VS Code with the **HashiCorp Terraform** extension is recommended |

You do **not** need gcloud, a Google account, or Docker. Docker is only for the dev container option.

## 2. Download providers from the Terraform Registry (once)

```powershell
python course.py setup
```

This step:

1. checks your Terraform and Python versions;
2. runs `terraform init` in `shared/terraform/`, which downloads the course's
   pinned providers from **registry.terraform.io** into `.course/plugin-cache/`;
3. creates `workspace/`.

After that, every `course check` initializes from the local cache in about a second.

### How the Registry and cache fit together

```
registry.terraform.io ──(setup, once)──▶ .course/plugin-cache/ ──▶ every lesson's init
                                                     ▲
                    shared/terraform/.terraform.lock.hcl (exact versions + checksums
                    for Windows, macOS and Linux, amd64 and arm64)
```

- **Pinned versions**: `hashicorp/google ~> 8.12` and `hashicorp/random ~> 3.7`,
  locked to exact versions in `shared/terraform/.terraform.lock.hcl`.
- If your lesson folder has no `.terraform.lock.hcl`, the checker supplies the
  shared one, so everyone gets byte-identical providers.
- Running `terraform init` yourself inside `workspace/NN-*` also works. It uses
  the Registry directly, which is fine and teaches the real workflow. To make
  your own runs use the cache too, set:

  ```powershell
  $env:TF_PLUGIN_CACHE_DIR = "$PWD\.course\plugin-cache"   # PowerShell, from the repo root
  ```
  ```bash
  export TF_PLUGIN_CACHE_DIR="$PWD/.course/plugin-cache"   # bash/zsh
  ```

### Behind a corporate proxy

Terraform honors `HTTPS_PROXY`. Set it before running setup:

```powershell
$env:HTTPS_PROXY = "http://proxy.example.com:8080"
python course.py setup
```

### Air-gapped classroom

On a connected machine:

```powershell
python course.py mirror D:\terraform-mirror
```

Copy the folder to each offline machine, then add the snippet that the command
prints to the Terraform CLI config: `%APPDATA%\terraform.rc` on Windows,
`~/.terraformrc` elsewhere. It looks like:

```hcl
provider_installation {
  filesystem_mirror {
    path    = "D:/terraform-mirror"
    include = ["registry.terraform.io/hashicorp/*"]
  }
}
```

## 3. Optional: dev container

Open the repo in VS Code → **Dev Containers: Reopen in Container**. The image
(`.devcontainer/`) pins Terraform, Python and tflint and runs `course.py setup`
on creation. GitHub Codespaces works the same way.

## 4. Verify

```powershell
python course.py start 01
python course.py check 01
```

The first check shows failing requirements. That's expected, because the starter
has TODOs. If `init` fails, see "Behind a corporate proxy" above.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `terraform was not found on PATH` | Install Terraform and open a new terminal |
| `init` fails with *could not connect to registry.terraform.io* | Check your connection or proxy, or use a mirror |
| `init` fails with *locked provider ... does not match* | Delete `.terraform.lock.hcl` in your workspace folder and re-check |
| `plan` fails with *401* or *invalid authentication* | A data source is trying to read live GCP data. See the lesson's README |
| `plan` fails with *No value for required variable* | Set it in `terraform.tfvars` |
| Colours look like `\033[32m` | Set `NO_COLOR=1`, or use Windows Terminal |
