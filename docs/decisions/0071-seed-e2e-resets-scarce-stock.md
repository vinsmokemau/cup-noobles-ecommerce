# ADR-0071: `seed_e2e` resets the scarce product to exactly two units

## Status

accepted (2026-11-09)

## Context

P13-V18 (stock lost between cart and pay) needs a product whose last two units a spec can buy.
`seed_e2e` only raised that product to two available units and never lowered it. The pending
orders of earlier runs hold units for 30 minutes and give them back when they expire, so a
second run on the same stack found a different number of units than two and the spec failed
(G62). ADR-0070 separated the E2E database, which makes a reset possible, but its Consequences
say G62 stays open if the scarce stock still drifts within one stack's life. Running the specs
twice on one stack showed that it does.

Alternatives considered:

- Rely on `make e2e-reset` before every run: slow (about 45 s) and a run that forgets it fails
  with a message that does not point at the cause.
- Change the spec so P13-V18 tolerates any stock: changes an assertion, which the project rules
  forbid for new work.

## Decision

Each run of `seed_e2e` sets the scarce product (`E2E-CHECKOUT-SCARCE`) to exactly two available
units. When the product has more than two available, the surplus is removed through the
inventory service (`adjust_stock`, reason `count_correction`), so the change has a ledger row.
When it has fewer, the existing behaviour stays: the missing units are received. Test code and
seed only; no spec assertion changes and no schema change.

## Consequences

- Re-running the seed resets the scarce product after a local run of the specs.
- Units held by a pending order cannot be removed (`AdjustmentBelowReserved`), so the seed only
  lowers available units, never reserved ones.
- Changing it later touches only `apps/catalog/e2e_seed.py` and its test.

## Source

OA-89; G62 (SPEC.md §2.4); ADR-0070.
