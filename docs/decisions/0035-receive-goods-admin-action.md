# ADR-0035: Goods are received through an admin action

## Status

accepted (2026-10-25)

## Context

Receiving goods is daily work (GE:T30, GE:T35, GE:§5.2), but the spec had no admin page for it (G20).

## Decision

1. A "Recibir mercancía" admin action: the staff member picks the variant and location and enters a quantity. In Release 1 it calls `receive_stock` with the staff user as `actor`.
2. A zero or negative quantity is a form error. `on_hand` is never an editable field.
3. In Release 2, for a pre-order variant the same action calls `receive_preorder_stock` (10.3).

## Consequences

- Every receipt writes one `receipt` ledger row naming the staff user (CR-05).
- T4.7 is built to this decision; the pre-order path is built in T10.3.
- Changing it later would touch T4.7, T10.3, P4-V19 and P15-V05.

## Source

G20; OA-34 (2026-10-25); T4.7.
