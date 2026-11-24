# Architecture

Meridian Books runs on five Terraform roots. Each has its own state and its own pipeline job.

| Root | Scope | What it owns |
|---|---|---|
| `bootstrap` | one project | The hardened, versioned state bucket every other root uses |
| `envs/platform` | organization | The landing zone: folders, guardrails, project factory, budgets, central logging |
| `envs/hub` | network projects | Hybrid network: HA VPN to on-prem, hub-and-spoke peering, Shared VPC, hybrid DNS |
| `envs/dev` | dev project | The shop, small: two zones, no DR footprint |
| `envs/prod` | prod project | The shop, production-sized: three zones, DR in us-east1 |

dev and prod call exactly the same modules; only `terraform.tfvars` differs.

```mermaid
flowchart TB
  subgraph platform["platform root - landing zone"]
    org[Organization] --> folder[Meridian folder: guardrails, folder IAM]
    folder --> fdev[dev folder]
    folder --> fprod[prod folder]
    folder --> fshared[shared folder]
    factory[Project factory: labels, budgets] --> projects[Projects]
    host[Shared VPC host project]
    sink[Folder log sink] --> logbucket[(Central log bucket, 400 days)]
  end

  subgraph prod["prod root - us-central1, DR in us-east1"]
    users((Customers)) --> lb[Global HTTP load balancer + Cloud Armor]
    lb --> web[Web MIG, 3 zones]
    lb -->|/api/*| api[Cloud Run catalog API]
    web --> ilb[Internal load balancer] --> app[App MIG, 3 zones]
    app --> sql[(Cloud SQL Postgres, REGIONAL)]
    api --> sql
    sql -. async replica .-> replica[(Cloud SQL replica in us-east1, REGIONAL)]
    api --> topic[Pub/Sub orders] --> worker[Cloud Run worker]
    gke[GKE Autopilot batch cluster] --> sql
    backups[(Backups bucket, NAM4 dual-region, turbo)]
    registry[(Artifact Registry, US multi-region)]
    kms[KMS keys] -.-> backups
  end

  dev["dev root - same modules, smaller, us-central1 only"]
  bootstrap["bootstrap root - Terraform state bucket"]

  bootstrap -. state .-> prod
  bootstrap -. state .-> dev
  projects -. hosts .-> prod
  prod -. logs .-> sink
```

## Request path

Customers reach the global load balancer, where Cloud Armor filters SQL injection and XSS and
rate-limits each client. Static pages come from the web MIG. `/api/*` goes to the Cloud Run catalog
service. Orders are published to Pub/Sub and processed by a private worker, retried with backoff,
and dead-lettered after a few attempts.

## Decisions

See [adr/](adr/) for why the platform looks like this, and
[failure-analysis.md](failure-analysis.md) for what happens when parts of it fail.
