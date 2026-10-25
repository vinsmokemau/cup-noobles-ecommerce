# ADR-0041: The mock payment provider's checkout and refund are built in Phase 8

## Status

accepted (2026-10-25)

## Context

G25: Phase 8 needs a payment provider before the mock exists. T1 creates a provider checkout and T16 refunds, but T1.11 creates only the interfaces and the mock is built in Phase 9 (T9.9). The alternatives were to keep G25 open with `xfail(strict=True)` tests, which would pass as soon as the methods exist and so fail the run, or to move order creation after Phase 9, which reorders two phases.

## Decision

1. `MockPaymentProvider.create_checkout(order)` and `refund(payment, amount_cents)` are built in Phase 8, in T8.10, ahead of the rest of the mock.
2. `create_checkout` stores a preference in the JSON store under `MOCK_STORE_DIR/payments/`, written atomically, and returns `SITE_URL/dev/payments/checkout/<preference_id>/`. `refund` records the refund in the store and returns a `RefundResult`.
3. Phase 9 (T9.9) completes the mock on top of these: `fetch_payment`, `find_payments`, `verify_webhook`, notifications and the simulator.
4. The tests of T8.10 and T8.2 are plain tests, with no `xfail`.

## Consequences

- T8.10 runs before T8.2, as the Phase 8 execution-order note says (OA-47).
- Changing this later would move two methods and the tests of P8-V01 and P8-V06; no schema or Verify ID changes.

## Source

G25; OA-48 (2026-10-25); T8.10, T8.2, T9.9, P8-V01, P8-V06.
