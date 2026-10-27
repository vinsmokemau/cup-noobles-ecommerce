# ADR-0051: An order has at most one shipment

## Status

accepted (2026-10-26)

## Context

The `shipment` table allows many rows per order, and T11 marks every undelivered shipment of the order delivered when it fires. The first shipment a carrier reports delivered would therefore move the whole order to `delivered` while other parcels were still on the road. Split shipments are not a case the store needs.

## Decision

1. An order has at most one shipment. `shipment.order_id` is unique.
2. The admin offers no second shipment on an order that already has one.
3. T11 marking the order's shipment delivered is therefore correct as written, and `sync_shipments` needs no "all shipments delivered" rule.

## Consequences

- `spec/schema.sql` turns `shipment_order_idx` into a unique index. The Django model and a migration must follow; no task covers that yet, so a task is proposed in the amendment.
- The `MOCK-<order number>-<n>` numbering of T10.9 keeps working, and `n` is always 1 for a real order. P10-V03 builds two shipments on one order directly through a factory and is left alone (CR-38); the unique index will reject that, so the follow-up task must adapt the test setup, not its assertions.
- Allowing split shipments later means dropping the unique index and giving T11 a rule for partial delivery.

## Source

OA-60; T10.1, T10.9, T10.11, 8.A (T11).
