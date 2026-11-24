# 0001. A landing zone with a project factory

Status: Accepted
Date: 2026-11-23

## Context

After the acquisition, more teams will build on Google Cloud. Until now every project was created by
hand in the console, with whatever labels, networks and permissions its creator chose. Finance can't
attribute costs, security can't see logs from new projects, and nobody can say which guardrails
apply where. We need every new project to start compliant without a ticket to the platform team.

## Decision

Create one Meridian folder under the organization with dev, prod and shared folders below it, and set
guardrails (organization policies) and access once on the folders. Projects are only created through
the `project-factory` module, which enforces mandatory labels, no default network, deletion
protection, a budget and Shared VPC attachment. This lives in its own root, `envs/platform`.

## Alternatives considered

- **Keep creating projects by hand, with a checklist.** Cheap to start, but checklists drift and
  nothing stops a project without labels or a budget.
- **One project per team with no folders.** Simpler, but guardrails and IAM would have to be repeated
  on every project, and forgotten on some.
- **A vendor landing-zone blueprint.** Complete, but far bigger than we need and hard to change.

## Consequences

New projects are consistent and appear in budgets and central logs on day one. The platform root
needs organization-level permissions, so its pipeline identity is the most powerful credential we
own and its environment requires two reviewers. Teams must ask for projects through a pull request,
which is slower than clicking in the console.
