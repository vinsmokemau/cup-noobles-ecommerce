# ADR-0067: P13-V01 asserts the hand-off, not the confirmed view

## Status

accepted (2026-11-06)

## Context

P13-V01 belongs to T13.3 and said the mobile delivery purchase "reaches the confirmed `gracias` view". The `gracias` page is built by T13.7, which the Phase 13 execution order places after T13.3. At T13.3 the page does not exist, so the assertion could not pass. Alternatives: build a minimal `gracias` in T13.3 (pulls T13.7's work forward and breaks one task per session), or reorder the tasks (changes the dependency graph).

## Decision

P13-V01 passes when the mobile delivery purchase reaches the simulator, "Aprobar con tarjeta" is pressed, the browser lands on `/pedido/{id}/gracias?t=…`, and `/dev/test/orders/` shows the order `paid`. The confirmed `gracias` view is asserted by P13-V13 in T13.7.

## Consequences

T13.3 can close without T13.7. The mobile purchase still proves the hand-off end to end through the order state. Nothing asserts the confirmed view on mobile until T13.7, where P13-V13 runs on both projects. Undoing this means moving the view assertion back to P13-V01 and running T13.7 first.

## Source

G57; OA-85.
