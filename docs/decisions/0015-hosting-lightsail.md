# ADR-0015: Hosting: AWS Lightsail, no staging

## Status

accepted (2026-10-21)

## Context

The launch scale is small (A4) and the owner operates the system alone (A15). The plan compared AWS Lightsail with a managed database, ECS Fargate with RDS, Fly.io, Railway or Render, and Hetzner with Coolify. The first has low operational burden and flat pricing; the ECS option brings a VPC, a load balancer and task definitions; the Hetzner option leaves patching and the database to the owner. The prices and their date are in Appendix C.2 and C.3, and are to be re-verified at signup (S1). The plan also chose not to run a second environment at launch.

## Decision

Production runs on AWS Lightsail: a container service, managed PostgreSQL, object storage and a CDN (Phase 20). There is no staging environment at launch. Local acceptance (Phase 15) and the production topology rehearsal take its place.

## Consequences

- Low operations burden and predictable cost.
- A change reaches production without a staging pass, so the full suite in CI and the local acceptance run carry that weight.
- Outgrowing Lightsail means moving containers and the database to another host; the scheduler needs a home in Lightsail too (G23).

## Source

Plan 3.5 and 20.9; Appendix C.2, C.3; S1; A4, A15.
