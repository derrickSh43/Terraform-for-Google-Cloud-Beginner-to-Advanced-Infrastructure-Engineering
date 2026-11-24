# Answer — Troubleshooting 18

**Symptom:** R18.6: `hub -> dev peering must export custom routes`.

**Root cause:** the hub learns `192.168.10.0/24` over BGP. That's a **dynamic (custom)
route** in the hub VPC. VPC peering exchanges only **subnet routes** by default. The hub's side
of the peering has `export_custom_routes = false`, so the on-prem route never crosses into dev,
even though dev's side has `import_custom_routes = true`.

**Fix:** in `envs/hub/main.tf`, `module "spoke_peering"`: `export_custom_routes = true`.

**Why both halves:** custom route exchange needs *export* on the side that has the routes (hub)
**and** *import* on the side that wants them (dev). Each network's owner opts in. Either one
missing blocks it.

**Can on-prem reply?** Only because the hub's Cloud Router also **advertises** the spoke ranges
(`advertise_mode = "CUSTOM"` with `10.10.0.0/16`, R18.5). Without that, on-prem would receive
dev's packets but have no route back. Hybrid connectivity always needs routes in **both**
directions. Check both sides' effective routes when debugging.
