# ADR-0043: Refunds are payment records: a partial refund keeps the order state, and a refund can be recorded after a terminal state

## Status

accepted (2026-10-25)

## Context

G26: T18 sent an order to `partially_refunded` and said it "stays fulfillable", but no transition leaves that state, so a partly refunded order could never ship or complete. G27: a refund after delivery (a return), or of a late payment on an expired or cancelled order, could not be applied, because `completed`, `expired` and `cancelled` accept no event. The alternatives were to add fulfillment transitions out of `partially_refunded` (more states and rows to test) and to keep the terminal states closed and handle those refunds outside the system.

## Decision

1. `partial_refund_issued` (T18) never changes the order state. It adds an `order_event` row and sets the payment's `refunded_cents`. The `partially_refunded` state stays in the enum and the schema but is not entered in Release 1.
2. `refund_issued` (T17) and `partial_refund_issued` (T18) are also accepted from `completed`, `expired` and `cancelled`, as recorded payment events: an `order_event` row and the payment's `refunded_cents`, with the order state unchanged. The guards are those of T17 and T18.
3. `refund_issued` from `paid`, `preparing`, `shipped` and `delivered` still moves the order to `refunded`. From `refunded`, every event stays illegal.
4. The code and its tests are changed by the new task T8.13, before the phase-close task T8.6a.

## Consequences

- A partly refunded order keeps moving through shipping and completion, with no new states to test.
- A return or a late-payment refund can be recorded without reopening the order.
- T8.13 is added to Phase 8 and T8.6a depends on it. No schema change, no new Verify ID.
- Changing this later would touch `TRANSITIONS`, the 8.A table, P8-V01, P8-V05, P8-V07 and the Phase 9 refund and reconciliation tasks.

## Source

G26, G27; OA-50, OA-51 (2026-10-25); T17, T18, T8.13, A12, P8-V01, P8-V07.
