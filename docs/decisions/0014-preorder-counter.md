# ADR-0014: Pre-order stock: a separate counter

## Status

accepted (2026-10-21)

## Context

Pre-orders sell units that have not arrived. Representing them as negative `on_hand` would break the rule that available stock is never negative (CR-04) and would mix promises with physical stock. Pre-orders are deferred to R2 (§1.2), but the schema columns stay in R1.

## Decision

Pre-order quantity comes from a separate counter on the `variant` and never touches shelf stock (CR-08). Physical stock changes only through the inventory services, with a ledger row (CR-05).

## Consequences

- Shelf stock keeps its invariants.
- R1 carries the columns but no pre-order services, UI or tests.
- Allocation order and tie-breaks (G9) and cancellation (G6) are deferred to R2.

## Source

Plan 10.A; CR-04, CR-08; A5, A6.
