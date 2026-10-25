# ADR-0037: The storefront shows a low-stock badge, with no counts

## Status

accepted (2026-10-25)

## Context

D10 asked whether the storefront shows exact stock counts, a low-stock badge, or only in or out of stock. G13 noted that D10 suggested a badge for "under 5", while T5.3 defines `low_stock` as `1 <= available <= 5`; the two differ only when exactly 5 units are available. T5.3 was built to the spec text with the §2.5 stand-in (badge, no counts).

Exact counts were ruled out because they leak stock levels to competitors and add nothing a badge does not tell a shopper. Showing only in or out of stock was ruled out because it hides the scarcity cue.

## Decision

1. D10: the public payload carries a status, never a count: `in_stock`, `low_stock` or `out_of_stock`.
2. G13: `low_stock` when `1 <= available <= 5`. With 5 units available the status is `low_stock`; with 6 it is `in_stock`.
3. The stand-in in §2.5 is now the decision, so D10 no longer blocks the launch checklist.

## Consequences

- T5.3 needs no code change. P5-V07 and P5-V08 assert this decision.
- Changing the threshold later touches `LOW_STOCK_MAX` in `api/apps/catalog/availability.py` and the P5-V07 boundary rows. Showing counts would also touch P5-V08 and the serializer.

## Source

D10, G13; OA-40 (2026-10-25); T5.3, P5-V07, P5-V08.
