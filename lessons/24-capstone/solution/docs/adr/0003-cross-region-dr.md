# 0003. Cross-region disaster recovery for prod data

Status: Accepted
Date: 2026-11-23

## Context

The business agreed recovery objectives for a regional outage: database RPO 5 minutes, backups RPO
15 minutes, container images RPO 0, with RTOs between one and four hours. Before lesson 22 every prod
data store lived only in us-central1, so a regional outage would lose data permanently, whatever
the RTO.

## Decision

Add a cross-region read replica of the prod database in us-east1, configured REGIONAL like its
primary so it is highly available as soon as it is promoted. Keep backups and audit logs in the NAM4
dual-region with turbo replication, encrypted with keys that live in the same location. Store
images in the US multi-region registry. dev keeps none of this: `dr_region = null` switches it off.

## Alternatives considered

- **Backups only, restore into another region.** Cheapest, but daily backups mean an RPO of a day.
- **A zonal replica.** Half the replica cost, but it was a single point of failure: the
  capstone's lesson 21 baseline caught it, and after promotion prod would have run without HA.
- **Active-active in two regions.** Lowest RTO, but the application would need multi-region writes.

## Consequences

Roughly double the database and backup storage cost in prod. Failover is a manual, rehearsed
procedure (promote the replica, repoint the application), so RTO depends on people following the
runbook. Replication lag must be monitored, or the RPO is a hope rather than a measurement.
