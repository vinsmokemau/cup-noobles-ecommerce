# ADR-0076: A provider refund carries an idempotency key built from the payment

## Status

accepted (2026-11-17)

## Context

A refund is sent to the provider inside a database transaction, on both paths: T16 of
`apply_event` (cancelling a paid order) and `refund_payment` (9.8, the admin refund). If a later
step of that transaction fails, the database rolls back but the provider's refund stays. A retry
then refunds again, unless the provider treats the call as one it has already seen. The mock
hides this (G45).

Mercado Pago's create-refund endpoint (`POST /v1/payments/{id}/refunds`) lists the
`X-Idempotency-Key` header as required, so the adapter sends a key either way. The store allows
partial refunds (9.8), so one payment can have several refunds that are all wanted: a key built
from the payment id alone would make the second partial refund look like a repeat of the first.

How long Mercado Pago remembers a key is not documented for this endpoint. Another Mercado Pago
endpoint (Point orders) documents 24 hours, and a 409 for a key reused with a different request.

Alternatives considered:

- Record the refund attempt before calling the provider, in a transaction of its own, and skip a
  payment that already has an open attempt: it does not depend on the provider, but it needs a
  new record in the data model, a migration, and a way to settle an attempt whose outcome is
  unknown (Mercado Pago has a "Get refunds list" endpoint for that).
- A random key for each call: satisfies the required header and protects nothing.

## Decision

`MercadoPagoProvider.refund` sends `X-Idempotency-Key: refund:<payment id>:<refunded_cents>`,
where `<payment id>` is the id of our `Payment` row and `<refunded_cents>` is its running total
before this refund.

- A retry after a rollback sends the same key, because the rollback restored the total.
- A second partial refund sends a different key, because the total has moved.

The adapter builds the key, so both paths are covered and the `PaymentProvider` interface does
not change. The mock is not changed.

Checked by P16-V07 (unit, the key the adapter sends) and P16-V08 (sandbox: the same refund sent
twice with one key leaves exactly one refund on the payment).

## Consequences

- No schema change and no new setting.
- The protection lasts as long as Mercado Pago remembers a key. A retry after that can refund
  again; for a full refund Mercado Pago refuses an amount above what is left of the payment.
- If P16-V08 fails in the sandbox, the key is not enough: the fallback is the first alternative
  above, which is a data model change and needs its own decision.
- A retry with a different amount sends the same key with a different request. What Mercado Pago
  answers is not documented for this endpoint; the adapter must not treat that answer as a
  refund made.
- Changing it later touches `MercadoPagoProvider.refund` and the two tests.

## Source

OA-103; G45 (SPEC.md §2.4); T16.5; T16.7; 9.8; T8.1.
