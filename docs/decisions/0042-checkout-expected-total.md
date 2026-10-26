# ADR-0042: A checkout whose expected total no longer matches is refused with the fresh totals

## Status

accepted (2026-10-25)

## Context

G4: a price can change between the last time the customer saw their total and the moment they press "Pagar". Until now the order was created at the new price and the customer found out on the payment page. The alternatives were to keep that behavior, which can charge more than the customer saw, and to refuse only a price rise, which leaves a price drop unannounced and adds a second path to test.

## Decision

1. `POST /api/checkout/` takes an optional integer `expected_total_cents`: the total the customer last saw.
2. After `create_order_from_cart` has re-validated the lines and computed the totals, a total that differs from `expected_total_cents`, up or down, returns 409 `{"code": "total_changed", "totals": {…}}` with the fresh totals. No order and no reservation is created. Without the field, nothing is compared.
3. A stock failure keeps its own 409 `lines_unavailable` and is checked first. An `Idempotency-Key` replay returns the existing order before the comparison.
4. The storefront sends the total it rendered, and a `total_changed` response re-renders the review section so the customer sees what they will pay (T13.6, P13-V19).
5. The backend part is the new task T8.12, which owns P8-V09.

## Consequences

- One extra click for the customer in a rare case; no charge above the total the customer saw.
- T8.12 is added to Phase 8 and T8.6a depends on it. P8-V09 moves from T8.4 to T8.12. No schema change.
- Changing this later would touch `create_order_from_cart`, the checkout view, P8-V09, P13-V19 and T13.6.

## Source

G4; OA-49 (2026-10-25); T8.4, T8.12, T13.6, P8-V09, P13-V19.
