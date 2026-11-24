# DNS peering: queries for the zone from this network are answered as if they
# came from the target network (the hub), which forwards them to on-prem.
resource "google_dns_managed_zone" "this" {
  name       = var.name
  dns_name   = "${var.domain}."
  visibility = "private"

  private_visibility_config {
    networks {
      network_url = var.network_id
    }
  }

  peering_config {
    target_network {
      network_url = var.target_network_id
    }
  }
}
