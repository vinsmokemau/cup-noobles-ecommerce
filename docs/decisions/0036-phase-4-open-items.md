# ADR-0036: Phase 4 open items: outbox helper, idempotent commit, expiry job, owner alert address

## Status

accepted (2026-10-25)

## Context

Four design gaps were open in Phase 4, each with a proposed resolution already built and tested: G2 (the outbox write helper), G15 (`commit_reservations` and repeats), G37 (who expires an unpaid order, before `apply_event` exists) and G38 (the address of the owner's alerts).

## Decision

1. G2: `enqueue_email()` is built in Phase 4 (T4.6). It writes an `email_outbox` row in the caller's transaction and does not send. Sending is T11.1.
2. G15: a second `commit_reservations` call for the same order is a no-op.
3. G37: in Phase 4 `expire_reservations` only releases lapsed holds. From Phase 8 (T8.6a) it also fires T5 through `apply_event`, and `advance_orders` stops firing T5. P4-V03 asserts the order state from Phase 8 on.
4. G38: an `OWNER_ALERT_EMAIL` setting (SPEC.md §4.7). A `.test` address in development; `prod.py` has no default, so production fails to start until the owner's monitored inbox is set.

## Consequences

- T4.1, T4.3 and T4.6 are built to these decisions, and the tests that waited on them no longer carry an `xfail` reason for them.
- T8.6a must call `apply_event` from `expire_reservations` and add the order-state assertion to the P4-V03 test.
- Changing item 3 later would touch T4.3, T8.6a, P4-V03 and P8-V04.

## Source

G2, G15, G37, G38; OA-35 to OA-38 (2026-10-25); T4.1, T4.3, T4.6.
