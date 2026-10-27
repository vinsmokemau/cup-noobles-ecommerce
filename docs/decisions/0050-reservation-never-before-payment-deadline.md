# ADR-0050: A reservation never expires before its order's payment deadline

## Status

accepted (2026-10-26)

## Context

`expire_reservations` picks orders by the hold's expiry, but T5 only passes when `payment_deadline_at` is in the past. While every method shared the card window, both came from the same moment. T9.5 gives SPEI and OXXO longer deadlines. A hold that lapsed before its order's deadline would make the job raise `GuardFailed` and log a stack trace for that order every 5 minutes, and the hold would stay. The alternative, making T5 ignore the deadline, would let an order expire while the customer still has a valid voucher.

## Decision

1. A reservation's `expires_at` is never earlier than its order's `payment_deadline_at`.
2. When a `pending` OXXO or SPEI payment extends the deadline, the held reservations and `payment_deadline_at` move together, in one transaction. Neither moves earlier.
3. `expire_reservations` logs a `GuardFailed` from T5 as a one-line warning, not an exception.
4. A test uses a method whose deadline is longer than the card window (P9-V09).

## Consequences

- T9.5 already works this way, so no code, schema or Verify ID changes.
- Changing it later would touch the deadline extension in `apps/payments/mapping.py` and `expire_reservations`.

## Source

OA-59; G48, T8.6a, T9.5, REQ-012.
