# ADR-0072: `seed_e2e` settles the holds of earlier runs

## Status

accepted (2026-11-10)

## Context

ADR-0071 made `seed_e2e` set the scarce product to exactly two available units. That fixes the
stock at the start of a run, but the pending orders of earlier runs still hold units until their
payment deadline. In `make test-all` the second consecutive run starts about 20 to 25 minutes
after the first one's E2E pass, so those holds lapse in the middle of the run. The scarce stock
then changes under P13-V18, and the spec fails (found while closing T13.16).

Alternatives considered:

- Run `make e2e-reset` between runs: slow, and a run that forgets it fails without pointing at
  the cause. It also does not meet the check "twice in a row on the same stack".
- Shorten the E2E reservation hold: changes a business value (the hold period), which only the
  owner sets.

## Decision

Before it sets the scarce product (`E2E-CHECKOUT-SCARCE`) to two available units, `seed_e2e`
settles every held stock reservation on that variant. A `pending_payment` order is cancelled
through `apply_event` (`cancelled_by_customer`, actor `seed_e2e`); a `draft` order has its holds
released. Orders in any other state hold nothing. Seed code only: no schema change, no spec
assertion changed, no business value changed.

## Consequences

- Every run starts with no hold that can lapse during it.
- The cancelled orders send their `order_cancelled` email to the E2E addresses, which the E2E
  stack never delivers outside the test mail.
- Changing it later touches only `apps/catalog/e2e_seed.py` and its test.

## Source

OA-90; G62 (SPEC.md §2.4); ADR-0070; ADR-0071.
