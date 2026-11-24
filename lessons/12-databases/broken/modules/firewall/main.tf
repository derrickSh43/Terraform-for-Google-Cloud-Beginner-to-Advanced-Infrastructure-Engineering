# Data-driven firewall: one rule per entry in var.rules.
resource "google_compute_firewall" "this" {
  for_each = var.rules

  name        = "${var.name_prefix}-${each.key}"
  description = each.value.description
  network     = var.network_id
  direction   = "INGRESS"
  priority    = each.value.priority

  source_ranges = each.value.source_ranges
  source_tags   = each.value.source_tags
  target_tags   = each.value.target_tags

  allow {
    protocol = each.value.protocol
    ports    = each.value.ports
  }
}
