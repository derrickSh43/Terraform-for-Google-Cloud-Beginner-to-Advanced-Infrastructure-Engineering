# Binary Authorization: GKE (lesson 15, challenge) only runs images from Meridian's registry.
resource "google_project_service" "binauthz" {
  service            = "binaryauthorization.googleapis.com"
  disable_on_destroy = false
}

resource "google_binary_authorization_policy" "this" {
  global_policy_evaluation_mode = "ENABLE" # allow Google-maintained system images

  admission_whitelist_patterns {
    name_pattern = "${var.registry}/*"
  }

  default_admission_rule {
    evaluation_mode  = "ALWAYS_DENY"
    enforcement_mode = "ENFORCED_BLOCK_AND_AUDIT_LOG"
  }

  depends_on = [google_project_service.binauthz]
}
