# Failure analysis (prod)

What is left of production when part of Google Cloud fails. The numbers come from the plan: VM
counts at **minimum** autoscaler size (the worst moment to lose a zone), with regional MIGs using
`EVEN` distribution so that one zone holds at most `ceil(n / zones)` VMs.

## Zone loss

| Workload | Kind | Zones | Minimum capacity | After losing a zone |
|---|---|---|---|---|
| `module.web.google_compute_region_instance_group_manager.this` | regional MIG | 3 | 6 | 4 |
| `module.app.google_compute_region_instance_group_manager.this` | regional MIG | 3 | 3 | 2 |
| `module.db.google_sql_database_instance.this` | Cloud SQL, REGIONAL | standby in a second zone | 1 | 1 |
| `module.db.google_sql_database_instance.replica` | Cloud SQL replica (us-east1), REGIONAL | standby in a second zone | 1 | 1 |

**Single points of failure: none.** The capstone baselines found one: lesson 22's DR replica was
`ZONAL`. It is now `REGIONAL` like its primary (see [ADR 0003](adr/0003-cross-region-dr.md)).

The web tier keeps 4 of 6 VMs, enough for normal traffic (load tests: 1 VM per 150 req/s, peak
500 req/s). The autoscaler adds VMs in the surviving zones within minutes.
