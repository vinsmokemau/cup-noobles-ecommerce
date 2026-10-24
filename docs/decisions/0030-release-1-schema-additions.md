# ADR-0030: Release 1 schema additions

## Status

accepted (2026-10-23)

## Context

Six open items proposed changes to `spec/schema.sql` that Release 1 needs: G3, G5, G28, G31, G33 and G34. The spec says to decide them before T2.1a, because a change decided after Phase 2 closes is an amendment plus a new migration. The owner chose the proposed resolution for each (OA-22 to OA-27). The alternatives were: no data model for featured products; no bin location; a separate table for idempotency keys; UTC for the order-number year; a purchase limit counted per email only; and no cost snapshot, with margin taken from the current cost. Each was ruled out because it left a Release 1 requirement unmet or brought a cost that was hard to undo once orders existed.

## Decision

1. **G28.** `product.is_featured` (boolean, default false) and `product.featured_position` (integer, default 0, not negative), with the partial index `product_featured_idx` over active featured products. Related products are those sharing the franchise or a category; they need no column.
2. **G34.** `stock_item.bin_location`, optional text with default `''`. Editing it writes no ledger row and doesn't touch `on_hand`.
3. **G3.** `order.cart_token`, `order.idempotency_key` and `order.idempotency_fingerprint`, all nullable and set together (`order_idempotency_complete`), with the partial unique index `order_idempotency_uq` over `(cart_token, idempotency_key)` where the key is not null. The fingerprint is the SHA-256 hex digest of the canonical request body. The same key with a different body returns 422 `idempotency_key_reused`. The key lives as long as its order and has no separate expiry.
4. **G5.** The store timezone is `America/Mexico_City`, for the order-number year and for displayed dates. Order numbers come from one Postgres sequence per year, created on first use. The sequences are database objects outside `spec/schema.sql`'s tables, so P2-V01 is unaffected.
5. **G31.** `variant.purchase_limit`, nullable integer greater than zero; `NULL` means no limit. The guard counts units in pending and paid-or-later orders whose email, phone or normalised shipping address matches, within `PURCHASE_LIMIT_WINDOW_DAYS`. The window length is a business value that the owner has not given. It stays with D15, and the setting has no default; tests set it.
6. **G33.** `order_line.unit_cost_cents`, nullable and not negative, copied from `variant.cost_cents` when the order is created. Admin CSV exports of orders, lines and shipments read it.

## Consequences

- `spec/schema.sql` is final for Release 1 before any migration exists, so T2.1a to T2.1c build it directly and no amendment migration is needed.
- T2.1a gains `is_featured`, `featured_position` and `purchase_limit`; T2.1b gains `bin_location`; T2.1c gains the idempotency columns and `unit_cost_cents`. G31's column sits on `variant`, so it moves from T2.1c's open items to T2.1a.
- The ⚠️ markers of P4-V20, P8-V03, P8-V08, P8-V12, P8-V20, P8-V21, P10-V24 to P10-V26, P12-V13 and P13-V24 are removed; those tests must pass in their phases.
- Changing any of these later is a migration. Changing the timezone after orders exist would make year boundaries inconsistent between old and new order numbers.
- D15 still has to supply the limit values and the window before launch (Phase 22).

## Source

G3, G5, G28, G31, G33, G34; OA-22 to OA-27. SPEC.md §4.4 and §6 Phase 2.
