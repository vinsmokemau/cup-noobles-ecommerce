# ADR-0019: CFDI issued by hand in Release 1

## Status

accepted (2026-10-21)

## Context

The plan had no CFDI in v1, but the owner's execution guide requires CFDI to the customer, possibly manual at first, and a global invoice (C-05). The owner asked for a suggestion and accepted manual issuing (OA-07). Integrating a PAC (authorized certification provider) is a larger build and a vendor decision.

## Decision

CFDI is issued by hand in R1 (A8). The store captures optional fiscal data at checkout, keeps a queue of requests, stores the folio, UUID, PDF and XML the owner uploads, emails them, exports the orders a global invoice needs, and flags refunds of invoiced orders. An `InvoiceProvider` interface has only a manual implementation, so a PAC can replace it later (ADR-0016).

## Consequences

- No PAC account or integration in R1.
- Fiscal fields and codes are placeholders until the accountant confirms them (D16, ADR-0002).
- Adding a PAC later is a new adapter plus its contract suite.

## Source

OA-07; A8; C-05; D3, D16.
