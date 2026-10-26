# ADR-0044: A failing webhook row is retried 10 times, and a notification timestamp is fresh within the tolerance on both sides

## Status

accepted (2026-10-26)

## Context

G7: a `webhook_event` row that fails processing stays unprocessed for `process_webhooks` to retry, but nothing capped the retries, so one bad row could be retried forever (R-20). G8: the signature check rejected timestamps older than `WEBHOOK_MAX_AGE_SECONDS`, but the spec said nothing about timestamps in the future, which a skewed clock at the provider or at our server would produce. The alternatives were to keep retrying without a cap and to reject every future timestamp. The first hides a permanent failure, and the second drops real notifications whenever the two clocks drift apart by a few seconds.

## Decision

1. `process_webhooks` retries a failing row up to 10 attempts, waiting longer between attempts (exponential backoff). After the 10th failed attempt the row is marked failed, is not retried again, and an alert is raised.
2. A notification timestamp `ts` is accepted when `abs(now − ts) <= WEBHOOK_MAX_AGE_SECONDS`. A timestamp older than that, or further in the future than that, returns 401.
3. The tests of P9-V10, P9-V13 and P9-V17 are plain tests, with no `xfail`.

## Consequences

- A permanently failing row stops after 10 attempts and is visible, instead of growing `attempts` for ever.
- A clock that drifts by less than 5 minutes in either direction no longer loses notifications.
- The backoff base and the representation of "failed" (no schema change) are technical choices, listed as judgment calls in the T9.3 report.
- Changing the cap or the tolerance later touches `process_webhooks`, `signing.verify` and the three tests above.

## Source

G7, G8; OA-53 (2026-10-26); 9.A rules 3 and 5, T9.3, P9-V10, P9-V13, P9-V17.
