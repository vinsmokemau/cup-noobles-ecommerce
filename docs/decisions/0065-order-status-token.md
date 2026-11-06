# ADR-0065: The order-status token

## Status

accepted (2026-11-05)

## Context

The landing pages `gracias`, `pendiente` and `error` must read the order's state, but a guest has only the guest lookup (6.7), which needs the order number and the email and allows 5 calls an hour per IP. A page that polls every 2 seconds cannot use it (G21). Alternatives not taken: raising the guest-lookup limit (it would weaken the protection of that endpoint), and a cookie session for guests (a new identity mechanism for one read).

## Decision

At T1 the API issues a signed order-status token for the order (Django signing) and carries it in the provider's `back_urls` as `?t=<token>`. `GET /api/orders/{public_id}/status/?t=<token>` returns the order's public status fields. It is read-only, is not subject to the guest-lookup limit, and returns the same 404 body for a missing order, an expired token and a tampered token. The token expires at the order's `payment_deadline_at`, so it reuses the D6 windows and adds no new number. The pay-retry endpoint (G22, T13.10) is authorised by the same token.

## Consequences

T13.9 builds it as written and P13-V26, P13-V13 and P13-V14 are plain tests with no `xfail`. A customer who opens a `back_url` after the deadline gets the 404 and must use the guest lookup or the email. Changing the lifetime later touches one function and its test. G22 stays open for the pay-retry endpoint.

## Source

G21; OA-83.
