# ADR-0070: The E2E stack uses its own database volume

## Status

accepted (2026-11-08)

## Context

The E2E stack (`docker-compose.e2e.yml`) and the development stack share one Postgres volume,
`pgdata`. Every E2E run writes test products, orders and stock into the same database as the
owner's development data. The only way to return the E2E data to a known state is to wipe that
volume, which would also delete the development data. While closing T13.7, P13-V18 could not be
re-run on the same stack because `seed_e2e` only raises the scarce product's stock and the
pending orders of earlier runs expire later; the stock had to be corrected by hand (G62).

Alternatives considered:

- Wipe `pgdata` before each E2E run: rules out the owner's development data.
- Make `seed_e2e` lower stock only: fixes G62 but leaves the shared volume and the pollution of
  the development data.
- Run the E2E stack under a separate Compose project name: works, but hides the separation in a
  flag that is easy to forget. A named volume in the E2E override is visible in the file.

## Decision

The E2E stack's database uses its own named volume, `pgdata_e2e`, set in
`docker-compose.e2e.yml`. The development volume `pgdata` is not used by the E2E stack. A new
`make e2e-reset` target wipes only `pgdata_e2e` and starts the E2E stack again, which migrates
and seeds it from nothing.

It is accepted when all three hold (P13-V30):

- after `make e2e-reset`, the scarce product shows 2 on hand and 0 reserved;
- `make test-all` run twice in a row on the same stack is green both times;
- the development database's row counts are unchanged after an E2E run.

Data already in `pgdata` from earlier E2E runs is not removed by this decision.

## Consequences

- E2E state can be reset at any time without touching development data.
- G62 stops recurring after a reset. It is closed by T13.16 when the checks pass; if the scarce
  stock still drifts within one stack's life, G62 stays open.
- The first start of the E2E stack is slower: it migrates and seeds from scratch.
- Reverting later would touch the E2E override, the Makefile and any data kept in two volumes.

## Source

OA-88; G63 (SPEC.md §2.4); G62.
