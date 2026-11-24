# Runs inside modules/ha-vpn (it declares configuration_aliases), with both provider configurations mocked.
mock_provider "google" {}

mock_provider "google" {
  alias = "peer"
}

mock_provider "random" {}

variables {
  name            = "test"
  region          = "us-central1"
  network_id      = "projects/a/global/networks/a"
  peer_network_id = "projects/b/global/networks/b"
  local_asn       = 64514
  peer_asn        = 64515
}

run "sessions_use_matching_link_addresses" {
  command = plan

  module {
    source = "./"
  }

  providers = {
    google      = google
    google.peer = google.peer
  }

  assert {
    condition     = google_compute_router_peer.local[0].peer_ip_address == "169.254.0.2"
    error_message = "This side should peer with .2 of the first link range."
  }

  assert {
    condition     = google_compute_router_interface.peer[1].ip_range == "169.254.0.6/30"
    error_message = "The other side should use .2 of the second link range."
  }
}

run "duplicate_ranges_rejected" {
  command = plan

  module {
    source = "./"
  }

  providers = {
    google      = google
    google.peer = google.peer
  }

  variables {
    link_ranges = ["169.254.0.0/30", "169.254.0.0/30"]
  }

  expect_failures = [var.link_ranges]
}

run "non_link_local_rejected" {
  command = plan

  module {
    source = "./"
  }

  providers = {
    google      = google
    google.peer = google.peer
  }

  variables {
    link_ranges = ["10.0.0.0/30", "169.254.0.4/30"]
  }

  expect_failures = [var.link_ranges]
}
