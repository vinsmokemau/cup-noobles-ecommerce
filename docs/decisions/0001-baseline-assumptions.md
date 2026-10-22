# ADR-0001: Baseline assumptions

## Status

accepted (2026-10-21)

## Context

The plan rests on assumptions that shape the schema, the scope and the infrastructure. They are cheap to reverse unless marked otherwise. The owner's answers rewrote several of them: A1 and A11 (no pickup, no counter sales; OA-08, OA-11) and A8 (manual CFDI; OA-07). A15–A19 were added for a one-person team, guest checkout, the pinned Design System and the public repository. Writing them down once stops each phase from re-deciding them.

## Decision

A1–A19 of SPEC.md §2.3 are the baseline, with their cost to change:

| Assumption | Cost to change later |
|---|---|
| A1 one warehouse location, not a pickup point | Low |
| A2 prices stored and displayed IVA-included | Low |
| A3 MXN only, `es-MX` only | Medium |
| A4 launch scale: one small server, one small database | Low |
| A5 pre-orders charged in full at order time (R2) | High |
| A6 an order with pre-order items ships complete (R2) | Medium |
| A7 flat shipping by zone and subtotal, one carrier | Low |
| A8 CFDI issued by hand in R1 | Medium |
| A9 no discounts; `discount_cents` is always 0 | Low |
| A10 the developer is weakest on frontend | n/a |
| A11 no counter sales (R2) | Low |
| A12 no returns workflow beyond a manual refund | Low |
| A13 Part A runs offline | Low |
| A14 each mock behaves like its real provider | Medium |
| A15 one maintainer | n/a |
| A16 guest checkout only in R1 | Medium |
| A17 Design System pinned at an exact version | Low |
| A18 public repository on GitHub Free | Low |
| A19 reports built by the owner from CSV exports | Low |

## Consequences

- A5 is the only High-cost assumption. It is deferred to R2, so R1 code does not depend on it.
- Changing an assumption is an amendment to SPEC.md §2.3, recorded by a new ADR that supersedes this one for that row.

## Source

SPEC.md §2.3; plan §1; OA-07, OA-08, OA-10, OA-11.
