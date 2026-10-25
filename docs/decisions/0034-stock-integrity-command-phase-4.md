# ADR-0034: The stock integrity command is built in Phase 4

## Status

accepted (2026-10-24)

## Context

P4-V07 tests `manage.py check_stock_integrity` in Phase 4, but the command was specified in plan task 21.7 (G24).

## Decision

1. The command is built in Phase 4 (T4.9). For every `stock_item` it asserts that the sum of its ledger deltas equals `on_hand`, and that `reserved` equals the units in its `held` stock reservations.
2. It is read-only. It exits non-zero and names each failing stock item.
3. Its daily line in `infra/crontab` is added in T4.9. T21.7 stays absorbed; T21.4 reports the result.

## Consequences

- The ledger invariant (CR-05, REQ-011) is checked from Phase 4 on, not only at production time.
- Moving the command back to Phase 21 would change T4.9, T21.7 and P4-V07.

## Source

G24; OA-33 (2026-10-24); T4.9.
