# ADR-0068: The purchase-limit window and which variants carry a limit

## Status

accepted (2026-11-07)

## Context

G31 (ADR-0030) built a per-customer purchase limit: a variant may carry `purchase_limit`, and the checkout guard counts that customer's units in pending and paid orders within `PURCHASE_LIMIT_WINDOW_DAYS`. The values were left open as D15. Window alternatives: 7 days (resellers can restock weekly), 30 days, 90 days (blocks regular repeat buyers for months). Assignment alternatives: no limit anywhere, a limit only on named variants, a default limit on every variant (wrongly limits normal products and loses sales).

## Decision

1. `PURCHASE_LIMIT_WINDOW_DAYS` is 30 in production. An order 31 days after the last is allowed; one at 29 days is counted.
2. Only the variants the owner names carry a limit, and the number of each is set in the admin at the opening stock count. A variant with an empty `purchase_limit` has no limit. There is no default limit.

## Consequences

The code keeps no default for the setting, so a deploy that omits it fails loudly while any variant carries a limit (§4.7); Phase 22 sets it to 30. The per-variant numbers are data the owner enters, not spec values. Tests keep their factory values. Changing the window later is a setting change; adding or removing a limit is an admin edit.

## Source

D15; OA-86 (2026-11-07); G31 and ADR-0030 for the mechanism.
