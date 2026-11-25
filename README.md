# Terraform for Google Cloud: Beginner to Advanced Infrastructure Engineering

Learn to design, secure, structure and troubleshoot real Google Cloud
infrastructure with Terraform, from your first bucket to an enterprise platform.

**No Google Cloud account. No credit card. No cloud bill.** Every lab is checked
locally with `terraform fmt`, `validate`, an offline `plan` and automated
requirement checks. The only network access is `terraform init` downloading
providers from the Terraform Registry (the setup step does that once), and the
app asking GitHub whether there's a newer version of the course.

> **The course's definition of success:** can you write, structure, validate and
> *explain* Terraform that would provision the intended GCP architecture?

---

## Quick start

You need **Terraform ≥ 1.9** and **Python ≥ 3.10**. Nothing else: no pip
packages, no gcloud.

```powershell
git clone https://github.com/derrickSh43/Terraform-for-Google-Cloud-Beginner-to-Advanced-Infrastructure-Engineering.git terraform-course
cd terraform-course
python course.py setup        # once: checks tools, downloads providers and the code editor
python course.py              # opens the course app in your browser
```

**The course app** puts everything in one window, so you don't need a separate editor or terminal:

| Left | Right |
|---|---|
| The lesson, then one task at a time: **Learn → Lab → Challenge → Troubleshoot → Done** | Your files in a VS Code-style editor (Monaco: Terraform highlighting, tabs, Ctrl+S, find/replace) |
| Each task's instructions, which requirements it's checked by, and the result of the last check, with hints | **▶ Check** (Ctrl+Enter) runs `terraform fmt`, `init`, `validate` and an offline `plan`, then the requirement checks. **Format** runs `terraform fmt`. Results, pipeline, plan and test output appear under the editor |

When a task passes, **Next task →** appears, and tasks that already pass are skipped. After the
lab come the challenge and a troubleshooting exercise (a broken copy opens in the editor), then
**Next lesson →**. Progress is saved in `workspace/.progress.json`. The app runs only on your
machine (`127.0.0.1`) and edits only files in `workspace/`. Stop it with Ctrl+C in its terminal.

```powershell
python course.py 05           # open the app at lesson 05
python course.py guide        # the same flow in the terminal, without a browser
```

Prefer single commands? They all still work:

```powershell
python course.py start 01                 # copy the lesson 01 starter into workspace/
python course.py check 01                 # validate your work (add --challenge, -v)
python course.py check-all --challenge    # every started lesson, one summary
```

Prefer a container? Open the repo in VS Code and choose **Reopen in Container**.
Terraform, Python and tflint are preinstalled. See [docs/SETUP.md](docs/SETUP.md).

## Getting updates

The app looks for fixes when it starts. When there are some, **⬆ Update available** appears at the top
right: it shows what's new, updates the course files, and restarts the app. Your work and progress are
in `workspace/`, which updates never touch. A lesson you've already started keeps the files you have.

If you cloned the course before this button existed, get it once with `git pull`, then restart the app.
A copy downloaded as a ZIP can't update itself, so clone it instead.

## What `course check` does

```
  PASS  fmt       all files are canonically formatted
  PASS  init      providers installed                  ← Terraform Registry, via shared cache
  PASS  validate  configuration is valid
  SKIP  lint      tflint not installed (optional)
  PASS  plan      Plan: 20 to add, 0 to change, 0 to destroy   ← fake credential, no GCP access
  PASS  tests     Success! 3 passed, 0 failed.         ← native terraform test, mock providers

Lab requirements
  PASS  R5.6   Connectivity: internet -> web VM on port 80 is allowed
  FAIL  R5.8   Connectivity: web VM -> app VM on port 8080 is allowed
        web VM -> app VM:8080/tcp should be ALLOWED, but is DENIED (implied ingress deny rule)
        hint: INGRESS allow tcp:8080 with source_tags = ["web"] and target_tags = ["app"]
```

Requirement checks read the **plan JSON**, so they test *what would be built*,
not how you typed it. Many different correct solutions pass.

## Course map

| Phase | Lessons | Status |
|---|---|---|
| **1 · Terraform and GCP Foundations** | 01 Terraform Basics · 02 GCP Foundations & basic IAM · 03 Compute VM · 04 VPC Fundamentals · 05 Networking I & Firewalls | ✅ ready |
| **2 · Core Infrastructure Engineering** | 06 State & modules · 07 Networking II · 08 Load balancing · 09 Autoscaling · 10 IAM · 11 Storage | ✅ ready |
| **3 · Modern Cloud Applications & Automation** | 12 Databases · 13 Serverless · 14 Event-driven · 15 GKE · 16 CI/CD · 17 Observability | ✅ ready |
| **4 · Advanced Engineering, Security & System Design** | 18 Advanced networking · 19 Security · 20 Advanced Terraform · 21 HA · 22 DR · 23 Enterprise platform · 24 Capstone | ✅ ready |

`python course.py list` shows live status. Roadmap and authoring status:
[docs/ROADMAP.md](docs/ROADMAP.md).

### One evolving project

Every lesson extends the same system, **Meridian Books**, a fictional online
bookstore. Each lesson's starter is the previous lesson's reference solution, so
you can always rejoin. Prefer to keep building on your own code?

```powershell
python course.py start 03 --from-mine
```

### Every lesson has the same shape

| File | Purpose |
|---|---|
| `README.md` | Concepts, architecture diagram, cost notes "if this were real" |
| `lab.md` | Guided lab with requirement IDs (R3.1, R3.2, ...) |
| `challenge.md` | Harder requirements (C3.x) with less guidance: `check NN --challenge` |
| `broken/` | A teammate's repo with a planted fault, to diagnose without rebuilding |
| `solution/`, `solution-challenge/` | One valid reference answer each: `python course.py solution NN` |

## Commands

| Command | What it does |
|---|---|
| `python course.py setup` | Check tools; download pinned providers into a shared cache |
| `python course.py list` | Lessons and your progress |
| `python course.py start NN [--from-mine] [--force]` | Copy a starter into `workspace/` |
| `python course.py check NN [--challenge] [--path DIR] [--json] [-v]` | Validate your work |
| `python course.py solution NN [--challenge]` | Where the reference solution is, and how to diff it |
| `python course.py mirror DIR` | Copy providers to a folder for air-gapped machines |
| `python course.py selftest [NN ...]` | (instructors) Prove every validator accepts solutions and rejects known-bad fixtures |

On Windows `course.cmd check 01` works too, and on macOS/Linux `./course check 01`.

## Safety

The checker **removes Google credentials** (`GOOGLE_APPLICATION_CREDENTIALS`,
`GOOGLE_CREDENTIALS`, impersonation settings) from Terraform's environment and
supplies a fake access token. It also forces a local backend. A course check
cannot read, create or change anything in a real Google Cloud project, even on
a machine that is logged in to gcloud.

## Found a bug?

This is a beta, tested on Windows so far. Please
[open an issue](https://github.com/derrickSh43/Terraform-for-Google-Cloud-Beginner-to-Advanced-Infrastructure-Engineering/issues)
with the lesson and step, your operating system, what you expected, and a screenshot or the check output.

## For instructors and authors

- [docs/AUTHORING.md](docs/AUTHORING.md): how to write a lesson, checks, fixtures and broken repos
- [docs/VALIDATION.md](docs/VALIDATION.md): how the offline pipeline works, and its limits
- CI runs `python course.py selftest` plus the coursekit unit tests on every push (`.github/workflows/course-ci.yml`)
