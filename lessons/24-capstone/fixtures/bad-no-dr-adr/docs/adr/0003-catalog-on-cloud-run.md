# 0003. Run the catalog API on Cloud Run

Status: Accepted
Date: 2026-11-23

## Context

The catalog API has spiky traffic: almost nothing at night, ten times the average during
promotions. Running it on the web MIG would mean paying for peak capacity all day, and the
team wants to deploy it independently of the storefront, several times a day, without touching VMs.

## Decision

Run the catalog as a Cloud Run service behind the global load balancer through a serverless NEG,
with `/api/*` routed to it. It runs as its own service account with no project roles.

## Alternatives considered

- **Another MIG.** Familiar, but slow to scale and billed for idle VMs around the clock.
- **GKE.** Flexible, but a cluster is a lot of platform to run for one stateless API.

## Consequences

Scaling to zero saves money at night, but the first request after idle is slower, so prod keeps one
instance warm. Deployments are image digests, which CI pins and the plan shows.
