# ADR-0012: Payments: Mercado Pago Checkout Pro

## Status

accepted (2026-10-21)

## Context

The store needs cards, OXXO cash, SPEI transfer and meses sin intereses (§1.2) without taking on card-data handling. The plan compared Mercado Pago, Stripe MX and PayPal MX. Mercado Pago supports OXXO and SPEI natively; the alternatives cover them partly or not at all. The fee figures and their date are in Appendix C.1, which also says to re-verify them at signup (S2). A hosted checkout keeps the store out of PCI scope beyond SAQ-A (§1.3).

## Decision

Payments go through Mercado Pago Checkout Pro, behind the `PaymentProvider` interface (ADR-0016). Part A uses a mock with the same interface (CR-22).

## Consequences

- Hosted checkout; no card data touches the store.
- Fees depend on settlement speed (D13) and on the installment terms the store absorbs (D7).
- Changing provider means a new adapter and a new contract run, not changes to domain code.

## Source

Plan 3.4; Appendix C.1; S2, D7, D13.
