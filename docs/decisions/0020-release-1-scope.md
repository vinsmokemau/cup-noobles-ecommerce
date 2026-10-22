# ADR-0020: Release 1 scope

## Status

accepted (2026-10-21)

## Context

The plan described a full v1 with pickup, counter sales, customer accounts and pre-orders. The owner's execution guide says the warehouse is never presented as a store (CR-47), and R1 is what is needed for the store to go live. The owner approved the cut and its two assumptions: no counter sales in R1, and customer accounts after R1 (OA-11).

## Decision

Release 1 is delivery only, with guest checkout. It has no pickup, no counter sales and no pre-order services; those and customer accounts move to Release 2 or later. The scope table of SPEC.md §1.2 is the authority. Tasks and Verify IDs tagged R2 keep their IDs and wait.

## Consequences

- Smaller first release; the traceability check requires tests only for R1.
- Pre-order and pickup schema columns stay in place.
- Moving an item into R1 is an amendment to §1.2.

## Source

OA-08, OA-11; C-04, C-06; SPEC.md §1.2.
