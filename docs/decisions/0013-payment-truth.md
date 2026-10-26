# ADR-0013: Payment truth: webhook plus reconciliation

## Status

accepted (2026-10-21)

## Context

A browser redirect can be forged, skipped or lost. A webhook can arrive twice, late or out of order, and its payload can lie. The plan compared trusting the redirect with trusting the webhook, and keying idempotency on the payment id with keying it on the notification (delivery) id. One payment produces several notifications, so a payment-id key would drop real state changes.

## Decision

The rules of plan 9.A, as CR-11 to CR-17:

1. The webhook is authoritative; the redirect is not.
2. A payload's amount and status are never trusted: the payment is fetched from the provider.
3. The signature is verified first, and stale timestamps are rejected.
4. Idempotency comes from the database, keyed on the provider's notification (delivery) id.
5. Webhooks are acknowledged fast; a row that fails is retried by `process_webhooks`.
6. Processing follows the fetched state, so seeing the same status twice is a no-op.
7. An approved payment moves the order only if its amount equals the order total.

## Consequences

- A reconciliation job covers lost webhooks.
- Retry limits (G7) and clock skew (G8) were resolved in ADR-0044, and a concurrent webhook and reconcile (G14) in ADR-0047.
- Order state changes still go through `apply_event` (CR-09).

## Source

Plan 9.A; CR-11 to CR-17.
