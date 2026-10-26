# ADR-0045: The inline webhook budget is 2000 ms

## Status

accepted (2026-10-26)

## Context

9.A rule 5 has the webhook endpoint process a notification inline within `WEBHOOK_INLINE_BUDGET_MS` and return 200 either way, and §4.7 left the value "Set in 9.3". T9.3 shipped with 2000 ms as a technical default. A short budget hands more rows to `process_webhooks`, which runs once a minute, so a notification would wait up to a minute longer to take effect. A long budget keeps a request open while the provider is slow and risks the provider's own timeout and a retry. The owner asked for 2000 ms to be the recorded value.

## Decision

1. `WEBHOOK_INLINE_BUDGET_MS` is 2000 in Part A and Part B. The default in `config/settings/base.py` and the §4.7 row say the same.
2. The budget is checked after `fetch_payment()` returns. A call that took longer rolls the attempt back and leaves the row unprocessed for `process_webhooks`. The endpoint still returns 200.

## Consequences

- No code or test changes: the default already is 2000, and the test that exercises the budget overrides it.
- Changing it later touches the setting, the §4.7 row and this ADR. Phase 16 should check it against the Mercado Pago timeout.

## Source

OA-54; 9.A rule 5, T9.3, §4.7.
