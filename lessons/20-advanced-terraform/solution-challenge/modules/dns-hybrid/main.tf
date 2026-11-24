# Hybrid DNS: Google Cloud resolves the corporate domain by forwarding to on-prem
# DNS servers, and on-prem can resolve Google Cloud private names through an
# inbound forwarder in the hub.

resource "google_dns_managed_zone" "corp" {
  name        = "corp-forwarding"
  dns_name    = "${var.corp_domain}."
  description = "Forward ${var.corp_domain} to on-prem DNS."
  visibility  = "private"

  private_visibility_config {
    networks {
      network_url = var.network_id
    }
  }

  forwarding_config {
    dynamic "target_name_servers" {
      for_each = var.onprem_dns_servers
      content {
        ipv4_address    = target_name_servers.value
        forwarding_path = "private" # through the VPN, not the internet
      }
    }
  }
}

resource "google_dns_policy" "inbound" {
  name                      = "hub-inbound-forwarding"
  enable_inbound_forwarding = true

  networks {
    network_url = var.network_id
  }
}
