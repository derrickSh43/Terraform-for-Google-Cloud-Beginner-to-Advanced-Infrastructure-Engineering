# 0002. Hub-and-spoke network with HA VPN to on-prem

Status: Accepted
Date: 2026-11-23

## Context

The warehouse system stays on-prem for at least two more years, and the shop needs to reach it
privately. Analytics also needs a network, and more spokes will follow. Peering every VPC with every
other VPC and running a VPN per environment would multiply tunnels, BGP sessions and overlapping
address ranges.

## Decision

Run a hub VPC in its own root, `envs/hub`, with an HA VPN gateway (two tunnels on two interfaces, BGP
with private ASNs) to on-prem. Spokes peer with the hub and import its custom routes, so on-prem routes
reach them. Analytics uses a Shared VPC subnet of the hub. Hybrid DNS forwards corp names to on-prem.
All address ranges are allocated from one plan and checked for overlaps.

## Alternatives considered

- **Classic VPN per environment.** Fewer moving parts, but no 99.99% SLA and duplicated tunnels.
- **Full-mesh VPC peering.** No transit through a hub, so on-prem routes would not reach the spokes,
  and the number of peerings grows quadratically.
- **Dedicated Interconnect.** Better bandwidth, but far too expensive for current traffic.

## Consequences

One place to manage hybrid connectivity and DNS. The hub becomes a shared dependency: a mistake there
affects every spoke, so its environment requires review. Peering is not transitive between spokes,
which is intended: spokes can't reach each other through the hub.
