"""Lesson 03 - Creating a Basic Compute VM: requirement checks."""

from coursekit.checks import one, require, requirement

SMALL_TYPES = {"e2-micro", "e2-small", "e2-medium"}


def _vm(plan):
    return one(plan, "google_compute_instance", "Compute Engine VM")


def _startup_script(vm) -> str:
    return vm.get("metadata_startup_script") or (vm.get("metadata") or {}).get("startup-script") or ""


# ------------------------------------------------------------------ lab
@requirement("R3.1", "One small, low-cost VM, declared as google_compute_instance.web",
             hint='resource "google_compute_instance" "web" with a shared-core type such as machine_type = "e2-micro".')
def small_vm(plan):
    vm = _vm(plan)
    require(vm.address == "google_compute_instance.web",
            f'Your VM is {vm.address}. Declare it as resource "google_compute_instance" "web" (the lesson test and '
            "later lessons use that name), and update everything that refers to it, such as outputs.tf")
    mt = vm.get("machine_type")
    require(mt in SMALL_TYPES, f"machine_type '{mt}' is not one of {sorted(SMALL_TYPES)} - keep course labs cheap")


@requirement("R3.2", "The VM's zone is inside the configured region",
             hint="zone = var.zone with a default such as \"us-central1-a\" (a zone, not a region).")
def zone_in_region(plan):
    vm = _vm(plan)
    region = plan.variable_value("region") or ""
    zone = vm.get("zone", "")
    require(zone.count("-") == 2 and zone.rsplit("-", 1)[0] == region,
            f"zone '{zone}' is not a zone inside region '{region}' (zones look like {region}-a)")


@requirement("R3.3", "Boot disk: Debian 12, small balanced disk",
             hint='boot_disk { initialize_params { image = "debian-cloud/debian-12"  size = 10  type = "pd-balanced" } }')
def boot_disk(plan):
    vm = _vm(plan)
    params = vm.get("boot_disk.0.initialize_params.0") or {}
    image = str(params.get("image", ""))
    require("debian-12" in image, f"Boot image '{image or 'not set'}' is not Debian 12")
    size = params.get("size")
    require(size is None or int(size) <= 20, f"Boot disk is {size} GB; 10-20 GB is plenty for a web server")
    require(params.get("type", "pd-balanced") in ("pd-balanced", "pd-standard"),
            f"Disk type '{params.get('type')}' - use pd-balanced (or pd-standard)")


@requirement("R3.4", "A startup script installs NGINX",
             hint='metadata_startup_script = file("${path.module}/scripts/startup.sh")')
def startup(plan):
    script = _startup_script(_vm(plan))
    require(script, "The VM has no startup script")
    require("nginx" in script.lower(), "The startup script does not install nginx")


@requirement("R3.5", "The VM runs as the dedicated web service account",
             hint="service_account { email = google_service_account.web.email  scopes = [\"cloud-platform\"] }")
def runs_as_sa(plan):
    vm = _vm(plan)
    sa = vm.blocks("service_account")
    require(sa, "No service_account block - the VM would run as the over-privileged Compute Engine default account")
    require(vm.references_type("google_service_account", "service_account"),
            "service_account.email should reference your google_service_account from lesson 02")
    scopes = sa[0].get("scopes") or []
    require(any("cloud-platform" in s for s in scopes), "Use the cloud-platform scope and let IAM roles limit access")


@requirement("R3.6", "Network tag and labels identify the web tier",
             hint='tags = ["web"] (firewall rules target this in lesson 5) and the standard labels plus role = "web".')
def tags_labels(plan):
    vm = _vm(plan)
    require("web" in (vm.get("tags") or []), "The VM has no \"web\" network tag")
    labels = vm.get("labels") or {}
    for key in ("app", "env", "managed_by"):
        require(key in labels, f"label '{key}' is missing")
    require(labels.get("role") == "web", f"label role is {labels.get('role') or 'missing'}, expected \"web\"")


@requirement("R3.7", "External IP and outputs for reaching the site",
             hint="network_interface { access_config {} } plus an output web_external_ip using ...access_config[0].nat_ip")
def external_ip(plan):
    vm = _vm(plan)
    nic = (vm.blocks("network_interface") or [{}])[0]
    require(nic.get("access_config"), "The network interface has no access_config, so the VM has no external IP")
    require("web_external_ip" in plan.outputs(), 'output "web_external_ip" is not defined')
    refs = plan.output_references("web_external_ip")
    require(any(r.startswith("google_compute_instance.") for r in refs), "web_external_ip should reference the VM")


@requirement("R3.8", "Shielded VM features are on",
             hint="shielded_instance_config { enable_secure_boot = true  enable_vtpm = true  enable_integrity_monitoring = true }")
def shielded(plan):
    cfg = _vm(plan).get("shielded_instance_config.0") or {}
    for key in ("enable_secure_boot", "enable_vtpm", "enable_integrity_monitoring"):
        require(cfg.get(key) is True, f"shielded_instance_config.{key} is not true")


@requirement("R3.9", "SSH access uses OS Login",
             hint='metadata = { enable-oslogin = "TRUE" } - IAM decides who can SSH, no hand-managed keys.')
def oslogin(plan):
    meta = _vm(plan).get("metadata") or {}
    require(str(meta.get("enable-oslogin", "")).upper() == "TRUE", "metadata enable-oslogin is not \"TRUE\"")


@requirement("R3.10", "The VM waits for the Compute API and its IAM roles",
             hint="depends_on = [google_project_service.apis, google_project_iam_member.web]")
def vm_dependencies(plan):
    vm = _vm(plan)
    require(vm.depends_on_type("google_project_service"), "The VM does not depend on the enabled APIs")
    require(vm.depends_on_type("google_project_iam_member"),
            "The VM does not wait for its IAM roles - early logs could be rejected")


# ------------------------------------------------------------------ challenge
@requirement("C3.1", "machine_type is a validated variable",
             hint="variable \"machine_type\" with a validation using contains([...], var.machine_type)", level="challenge",
             test="machine_type.tftest.hcl")
def machine_type_var(plan):
    require("machine_type" in plan.variables(), 'variable "machine_type" is not declared')
    require("var.machine_type" in _vm(plan).references("machine_type"), "The VM's machine_type should be var.machine_type")


@requirement("C3.2", "Startup page is rendered from a template with the environment name",
             hint='templatefile("${path.module}/scripts/startup.sh.tftpl", { environment = var.environment })',
             level="challenge")
def templated_script(plan):
    vm = _vm(plan)
    script = _startup_script(vm)
    env = plan.variable_value("environment") or ""
    refs = vm.references("metadata_startup_script") + vm.references("metadata")
    require("var.environment" in refs or any(r.startswith("local.") for r in refs),
            "The startup script is not rendered with var.environment")
    require(env and env in script, f"The rendered startup script does not contain the environment name '{env}'")


@requirement("C3.3", "Project-wide SSH keys are blocked",
             hint='metadata: block-project-ssh-keys = "TRUE"', level="challenge")
def block_keys(plan):
    meta = _vm(plan).get("metadata") or {}
    require(str(meta.get("block-project-ssh-keys", "")).upper() == "TRUE", "block-project-ssh-keys is not \"TRUE\"")


@requirement("C3.4", "Non-production VMs use Spot provisioning",
             hint='scheduling { provisioning_model = "SPOT" ... } when var.environment != "prod"', level="challenge")
def spot(plan):
    sched = _vm(plan).get("scheduling.0") or {}
    env = plan.variable_value("environment")
    if env == "prod":
        require(sched.get("provisioning_model", "STANDARD") == "STANDARD", "Production must not use Spot VMs")
    else:
        require(sched.get("provisioning_model") == "SPOT", f"environment '{env}' VM is not a Spot VM")
