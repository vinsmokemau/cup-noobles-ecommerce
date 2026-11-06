# ADR-0066: The pay-retry endpoint

## Status

accepted (2026-11-06)

## Context

A customer whose payment was rejected, or who closed the provider page, lands on `error` or `pendiente` with the order still `pending_payment` and its stock reserved. No endpoint gave them a new payment session for that order (G22). Retrying from the cart cannot work: the cart is converted at checkout (ADR-0049), so a second checkout would be refused, and allowing it would risk a second order holding a second set of stock.

## Decision

`POST /api/orders/{public_id}/pay/`, authorised by the order-status token (ADR-0065), returns a fresh `checkout_url` from `payment_provider().create_checkout(order)` while the order is `pending_payment`. It keeps the order's reservations and its `payment_deadline_at`. Any other state returns 409.

## Consequences

T13.10 builds it as written. P13-V27 and P13-V15 are plain tests with no `xfail`. Each retry adds a payment attempt for the order. The order's deadline does not move, so a retry cannot extend the hold. Changing this later touches one view and its test.

## Source

G22; OA-84.
