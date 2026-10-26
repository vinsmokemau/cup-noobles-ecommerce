# ADR-0011: Cart: server-side, prices frozen once

## Status

accepted (2026-10-21)

## Context

A client-side cart needs localStorage sync and can show or submit a stale price. Prices change between the moment a customer adds an item and the moment they pay (G4). The plan compared a client-side cart against a server-side one.

## Decision

1. The cart lives in the database. The client holds only an opaque cart token in a cookie.
2. The cart stores no prices (CR-03). Totals are computed in one function, `orders/pricing.py::compute_totals`, which the cart, checkout and order creation all call (CR-02).
3. Prices are frozen once, when the order is created.

## Consequences

- No stale price lives on the client.
- Every cart view reads the database.
- A price change between the last view and payment must be surfaced to the customer (G4, resolved by ADR-0042).

## Source

Plan 7.3; CR-02, CR-03.
