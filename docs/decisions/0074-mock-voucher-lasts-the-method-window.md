# ADR-0074: A mock voucher lasts the method's window

## Status

accepted (2026-11-15)

## Context

SPEC.md 9.5 said two things about a mock OXXO or SPEI voucher in one sentence: it expires
`RESERVATION_TTL_OXXO_HOURS` (SPEI: `RESERVATION_TTL_SPEI_HOURS`) after creation, and it mirrors
the preference expiry the real adapter requests in 16.2, which is the order's payment deadline,
the 30-minute card window. The simulator followed the second: a voucher made with "Pagar en OXXO"
lasted 30 minutes and its order 2 hours 30 minutes, not the 72 hours plus 2 of the D6 stand-in
(§2.5). The seeded OXXO order of the demo dataset (15.A) expired 2 hours 30 minutes after
`seed_demo` (G74, found while building T15.1).

Alternatives considered:

- Keep the simulator as it was and make 9.5 say the mock voucher expires with the checkout: no
  code change, but the OXXO window setting does nothing in Part A, and the demo's OXXO order
  (demo steps 8 and 13) is gone unless the data was seeded in the last 2 hours 30 minutes.

## Decision

The simulator gives a pending payment a voucher that expires the method's window after the
voucher's creation: `RESERVATION_TTL_OXXO_HOURS` for OXXO and `RESERVATION_TTL_SPEI_HOURS` for
SPEI. The order's deadline and holds follow 9.5 as before: for OXXO, the voucher's expiry plus
the 2-hour grace. 9.5 no longer says "mirroring the preference expiry".

Checked by `test_pending_payment_carries_a_voucher_that_lasts_the_method_window`
(`api/tests/api/payments/test_simulator.py`) and by `test_seed_demo_guest_order_history`.

## Consequences

- With the dev defaults, an order paid with "Pagar en OXXO" holds its stock for 74 hours, and the
  seeded OXXO order stays pending that long.
- The D6 values are exercised in Part A: changing a window changes what the simulator issues.
- 16.2 still sets only the preference's expiry. How the real provider is asked for a voucher that
  lasts the same window is open (G76); until it is answered the mock and the real provider may
  differ on this point.
- Changing it later touches `voucher_lifetime` in `api/apps/payments/devtools/outcomes.py`, the
  two tests above and the 9.5 sentence.

## Source

OA-97; G74 (SPEC.md §2.4); 9.5; D6 (§2.5).
