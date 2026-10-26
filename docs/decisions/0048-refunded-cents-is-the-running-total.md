# ADR-0048: A refund sets the payment's `refunded_cents` to the running total

## Status

accepted (2026-10-26)

## Context

T17 and T18 of 8.A say "Set `refunded_cents` on payment", and `_effects_refund` stores the value the caller passes. The table did not say whether that value is the running total or only the new refund. If a caller passed the new amount, a second partial refund would overwrite the first and the payment would under-report what was returned. The alternative, having `_effects_refund` add the amount, would make the webhook path (which passes the provider's own total) wrong.

## Decision

1. The `refunded_cents` an event carries is the running total: the payment's current `refunded_cents` plus the new refund.
2. The guards of T17 and T18 compare that total with the payment's `amount_cents`: equal is a full refund, and greater than 0 and less than is partial.
3. The refund service picks `refund_issued` or `partial_refund_issued` from that total, so two partial refunds that sum to the payment end in `refunded`.

## Consequences

- T9.8 already works this way, and the webhook path passes the provider's total, so no code changes.
- A test issues two partial refunds in a row and checks the total after each (P9-V15).
- Changing it later would touch `_effects_refund`, the refund service and the mapping.

## Source

OA-57; G46, T8.13, T9.8, 8.A rows T17 and T18, REQ-032.
