# HA VPN between two Google Cloud networks (here: the hub and a simulated on-prem
# data centre in another project). Two gateways x two interfaces = two tunnels per
# side, each with a BGP session, for the 99.99% SLA.

resource "google_compute_ha_vpn_gateway" "local" {
  name    = "${var.name}-gw"
  region  = var.region
  network = var.network_id
}

resource "google_compute_ha_vpn_gateway" "peer" {
  provider = google.peer

  name    = "${var.name}-peer-gw"
  region  = var.region
  network = var.peer_network_id
}

resource "google_compute_router" "local" {
  name    = "${var.name}-router"
  region  = var.region
  network = var.network_id

  bgp {
    asn               = var.local_asn
    advertise_mode    = "CUSTOM"
    advertised_groups = ["ALL_SUBNETS"]

    # Also announce the spokes (peered VPCs) so the other side can reach them.
    dynamic "advertised_ip_ranges" {
      for_each = var.advertised_ranges
      content {
        range = advertised_ip_ranges.value
      }
    }
  }
}

resource "google_compute_router" "peer" {
  provider = google.peer

  name    = "${var.name}-peer-router"
  region  = var.region
  network = var.peer_network_id

  bgp {
    asn = var.peer_asn
  }
}

# BGP sessions are authenticated too (MD5), with generated keys.
resource "random_password" "bgp_md5" {
  count   = 2
  length  = 24
  special = false
}

# One pre-shared key per tunnel pair, generated - never typed, never committed.
resource "random_password" "psk" {
  count   = 2
  length  = 32
  special = false
}

resource "google_compute_vpn_tunnel" "local" {
  count = 2

  name                  = "${var.name}-tunnel-${count.index}"
  region                = var.region
  vpn_gateway           = google_compute_ha_vpn_gateway.local.id
  vpn_gateway_interface = count.index
  peer_gcp_gateway      = google_compute_ha_vpn_gateway.peer.id
  shared_secret         = random_password.psk[count.index].result
  router                = google_compute_router.local.id
  ike_version           = 2
}

resource "google_compute_vpn_tunnel" "peer" {
  provider = google.peer
  count    = 2

  name                  = "${var.name}-peer-tunnel-${count.index}"
  region                = var.region
  vpn_gateway           = google_compute_ha_vpn_gateway.peer.id
  vpn_gateway_interface = count.index
  peer_gcp_gateway      = google_compute_ha_vpn_gateway.local.id
  shared_secret         = random_password.psk[count.index].result
  router                = google_compute_router.peer.id
  ike_version           = 2
}

# BGP over link-local /30s: .1 on this side, .2 on the other.
resource "google_compute_router_interface" "local" {
  count = 2

  name       = "${var.name}-if-${count.index}"
  router     = google_compute_router.local.name
  region     = var.region
  ip_range   = "${cidrhost(var.link_ranges[count.index], 1)}/30"
  vpn_tunnel = google_compute_vpn_tunnel.local[count.index].name
}

resource "google_compute_router_peer" "local" {
  count = 2

  name            = "${var.name}-bgp-${count.index}"
  router          = google_compute_router.local.name
  region          = var.region
  peer_ip_address = cidrhost(var.link_ranges[count.index], 2)
  peer_asn        = var.peer_asn
  interface       = google_compute_router_interface.local[count.index].name

  md5_authentication_key {
    name = "bgp-key-${count.index}"
    key  = random_password.bgp_md5[count.index].result
  }
}

resource "google_compute_router_interface" "peer" {
  provider = google.peer
  count    = 2

  name       = "${var.name}-peer-if-${count.index}"
  router     = google_compute_router.peer.name
  region     = var.region
  ip_range   = "${cidrhost(var.link_ranges[count.index], 2)}/30"
  vpn_tunnel = google_compute_vpn_tunnel.peer[count.index].name
}

resource "google_compute_router_peer" "peer" {
  provider = google.peer
  count    = 2

  name            = "${var.name}-peer-bgp-${count.index}"
  router          = google_compute_router.peer.name
  region          = var.region
  peer_ip_address = cidrhost(var.link_ranges[count.index], 1)
  peer_asn        = var.local_asn
  interface       = google_compute_router_interface.peer[count.index].name

  md5_authentication_key {
    name = "bgp-key-${count.index}"
    key  = random_password.bgp_md5[count.index].result
  }
}
