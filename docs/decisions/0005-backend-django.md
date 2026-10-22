# ADR-0005: Backend: Django and DRF

## Status

accepted (2026-10-21)

## Context

The owner is the only developer (A15) and also needs a back office for catalog, stock, orders, refunds and the manual CFDI queue (A8). The plan compared FastAPI, Go and Node with Medusa. The first two would need an admin, authentication and migrations built by hand. Medusa brings its own model of orders and stock. Django ships an ORM with migrations, sessions and an admin.

## Decision

Django 5 with Django REST Framework is the backend. The Django admin is the back office and keeps its default look (§1.3). The OpenAPI schema is generated from DRF and snapshotted (ADR-0009).

## Consequences

- No separate back-office application to build.
- Business logic lives in services, and the admin calls them instead of writing state directly (CR-05, CR-09).
- Leaving Django would mean rebuilding the admin, authentication and migrations.

## Source

Plan 3.2; A15.
