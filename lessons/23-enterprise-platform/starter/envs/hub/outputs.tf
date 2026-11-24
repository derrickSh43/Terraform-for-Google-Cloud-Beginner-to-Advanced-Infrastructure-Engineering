output "hub_network_id" {
  description = "Hub VPC ID (spokes peer with it)."
  value       = module.hub_network.network_id
}

output "vpn_tunnels" {
  description = "HA VPN tunnels on the hub side."
  value       = module.vpn.tunnel_names
}
