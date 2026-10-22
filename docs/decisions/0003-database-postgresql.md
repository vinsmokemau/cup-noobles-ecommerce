# ADR-0003: Database: PostgreSQL with JSONB

## Status

accepted (2026-10-21)

## Context

The store needs transactional integrity for money, stock and order state: row locks (`SELECT … FOR UPDATE`, CR-07, CR-09), `CHECK` constraints (CR-01), partial unique indexes for idempotency (CR-14), and a flexible attribute store for the catalog (ADR-0004). The plan compared MongoDB and MySQL. A document store gives up the constraints and the locking that the inventory and payment rules rely on. MySQL offers weaker JSON and partial-index support for the same needs.

## Decision

PostgreSQL 16 is the single source of truth, with JSONB for product attributes. Tests run on PostgreSQL only and abort on any other database (CR-40).

## Consequences

- Constraints, locks and partial indexes carry the invariants of Phases 2, 4, 8 and 9.
- Local and CI runs need a PostgreSQL service.
- Moving to another database later would rewrite the schema, the constraints and the concurrency tests.

## Source

Plan 3.1; CR-40.
