# ADR-0049: A cart is converted at checkout (T1), in the order's transaction

## Status

accepted (2026-10-26)

## Context

T8.4 creates an order from a cart but leaves `cart.converted_order` unset, and SPEC.md did not say when a cart converts. The owner postponed the question to Phase 9. Two options were weighed:

- **At payment approval.** Abandoned payments leave the cart reusable, but the same cart can be checked out again under a new `Idempotency-Key`, creating a second order that holds a second set of stock.
- **At T1 (checkout).** A second checkout from the cart is refused. A customer who abandons the payment pays again through the pay-retry endpoint of G22 (T13.10), so the cart is not needed for that.

The first suggestion was approval. G22's proposal already said "converted at T1", and the pay-retry endpoint removes the one advantage of converting later, so T1 was recommended and the owner chose it.

## Decision

1. `cart.converted_order` is set to the new order in the same transaction as T1. A failed checkout leaves the cart open.
2. A second checkout from a converted cart creates no order and no reservation.
3. A repeat with the same `Idempotency-Key` and body still returns the original order: the lookup uses the cart token and key, not an open cart.
4. A converted cart is treated as gone by the cart endpoints, and `purge_stale_carts` keeps it.

## Consequences

- New task T9.16 and Verify ID P9-V23. No schema change: the column and its foreign key exist.
- Phase 13's pay-retry endpoint (T13.10) is what lets a customer pay again; it stays open under G22.
- Changing it later touches `create_order_from_cart`, the checkout view's replay lookup and the cart lookup.

## Source

OA-58; G22 (cart half), T8.4, REQ-021.
