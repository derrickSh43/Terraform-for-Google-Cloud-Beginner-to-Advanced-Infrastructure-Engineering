output "tunnel_names" {
  description = "Tunnels on this side."
  value       = google_compute_vpn_tunnel.local[*].name
}
