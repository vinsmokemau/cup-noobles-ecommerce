# ADR-0047: A webhook and a reconciliation run on one approval move the order once, and the second is a no-op

## Status

accepted (2026-10-26)

## Context

A webhook and `reconcile_payments` (9.7) can process the same approved payment at the same moment. Both take the order row lock; the one that waits then finds the order already paid, and the state machine would refuse a second `payment_approved` with `IllegalTransition`. That would surface as an error for a case that is expected and harmless.

## Decision

1. When the order already reflects the fetched status, the second processor records `webhook_no_op` and raises nothing. Both paths share one function, so the rule is the same for each.
2. The check runs after the order row is locked and the order is re-read, so the winner is whichever takes the lock first.

## Consequences

- T9.4's mapping already behaves this way (9.4 rule 2), and T9.7 reuses it, so no code changes.
- P9-V14 passes as written and carries no `xfail`.

## Source

OA-56; G14, 9.7, P9-V14, REQ-022, REQ-031.
