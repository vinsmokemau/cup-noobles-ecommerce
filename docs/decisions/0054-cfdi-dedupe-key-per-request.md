# ADR-0054: The `cfdi_issued` dedupe key is per invoice request

## Status

accepted (2026-11-01)

## Context

T11.2 sets the dedupe key of once-per-order emails to `f"{order.id}:{template}"`. T11.8 applied the same formula to `cfdi_issued`, but P11-V11 says the email is queued once per issued request, and T10.14 already builds `cfdi_issued:{request.pk}`. `invoice_request` has no uniqueness on the order, so an order can have more than one request (for example a corrected invoice). The order-level key would silently drop the email of every request after the first. Alternative: keep the T11.8 key and change T10.14 and P11-V11; ruled out because it removes a working behavior to follow one sentence.

## Decision

1. The `cfdi_issued` dedupe key is `f"cfdi_issued:{request.pk}"`: one email per issued invoice request.
2. T11.8 states this key. No code changes: T10.14 already builds it.
3. The other keys that cannot be per order keep their own formats: `refund_issued` (per payment and running total), `oxxo_voucher` (per payment) and `low_stock_report` (per day).

## Consequences

- Re-saving or redelivering the same request queues nothing new; a second issued request gets its own email.
- Changing it later touches `apps/invoicing/services.py`, T11.8 and P11-V11.

## Source

C-15; OA-65; SPEC.md T10.14, T11.2, T11.8, P11-V11.
