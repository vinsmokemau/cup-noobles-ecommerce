# ADR-0053: `send_outbox` claims rows with `SKIP LOCKED`

## Status

accepted (2026-10-31)

## Context

`send_outbox` runs every minute and reads pending `email_outbox` rows without claiming them, so a run that outlasts a minute, or two runs started together, can send one email twice. REQ-022 requires every scheduled job to be safe to run concurrently with itself. Alternatives: a `claimed_at` column (a schema change, and a crashed run leaves rows stuck until a timeout), or a Postgres advisory lock for the whole job (a second run does nothing, so a slow run delays every other email).

## Decision

1. For each pending row, `send_outbox` opens a transaction and selects it with `SELECT … FOR UPDATE SKIP LOCKED`, re-checking that it is still unsent and under the attempt cap.
2. A row another run holds is skipped.
3. The send, and the `sent_at` or `attempts` update, happen inside that transaction, so the lock is held for the whole attempt.
4. P11-V10 is a plain test, with no `xfail`.

## Consequences

- No schema change; `webhook_event` processing already works this way (ADR-0044).
- A send that hangs holds one row's lock, not the whole queue.
- If the process dies mid-send, the lock is released and the row is sent again by the next run, which can duplicate one email in that crash case.

## Source

G17; OA-64; SPEC.md §4.8, REQ-022, T11.1, P11-V10.
