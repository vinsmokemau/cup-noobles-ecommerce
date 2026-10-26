# ADR-0046: A voucher for an expired order is cancelled at the provider, and the order stays expired

## Status

accepted (2026-10-26)

## Context

Checkout (T1) reserves stock for the card window, 30 minutes, before the payment method is known. A customer who spends longer than that on the provider page and then generates an OXXO or SPEI voucher produces a `pending` notification for an order that is already `expired`, with its stock released. T9.5 alerts a person and leaves the order alone, but the voucher stays valid, so the customer could still pay for an order the store cannot fulfil and a person would refund it by hand.

Three options were put to the owner. Alerting only leaves every late voucher to a person. A separate checkout-session TTL holds stock longer for customers who never pay and changes T1 and the hold times. Cancelling the voucher closes the risk and changes only the payment provider interface.

## Decision

1. A `pending` or `in_review` OXXO or SPEI payment for an order that is `expired` or `cancelled` raises an alert, leaves the order as it is, and is cancelled at the provider through `PaymentProvider.cancel_payment(provider_payment_id)`.
2. `cancel_payment` is idempotent. If the provider call fails, the failure is raised like any webhook failure, so the row is retried under ADR-0044.
3. There is no separate checkout-session TTL. T1 keeps `RESERVATION_TTL_CARD_MINUTES`.
4. T9.15 builds the interface method, the mock and the call. T16.3 builds the Mercado Pago method.

## Consequences

- A customer cannot pay cash for an order whose stock was released. A card payment approved late is a different case and still follows 9.4 rule 3.
- The payment interface gains a method, and the Phase 16 adapter must implement it.
- A customer who generates a voucher after 30 minutes loses the order and must check out again. If this proves common, a checkout-session TTL can be added later without undoing this decision.

## Source

OA-55; G11, 9.5, P9-V21.
