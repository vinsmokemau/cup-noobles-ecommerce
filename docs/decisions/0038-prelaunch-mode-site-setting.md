# ADR-0038: Pre-launch mode is a database flag edited in the admin

## Status

accepted (2026-10-25)

## Context

G32: the store must be live, with real test purchases by staff, while the catalog stays hidden from the public, and then everything is published at once. Catalog responses are cached publicly for 60 seconds (T5.6), so a hidden catalog must never carry `Cache-Control: public` (R-19). The spec left two things open: where the switch lives, and what anonymous requests get while it is on.

Where the switch lives. An environment variable was ruled out: going live would need a redeploy, staff could not flip it, and demo step 10 ("Admin + a private window") could not pass. A database flag edited in the admin has none of these limits, at the cost of one small table.

The response. A `200` with an empty catalog was ruled out because a CDN or crawler could take it for a real, empty catalog.

## Decision

1. The switch is the `prelaunch_mode` boolean of `site_setting`, a table with a single row (`id = 1`), edited in the admin. It is off until staff turn it on.
2. While it is on, an anonymous request to `/api/catalog/*` gets `503` with the JSON body `{"prelaunch": true}` and `Cache-Control: no-store`.
3. While it is on, a request with a logged-in staff session gets the normal catalog with `Cache-Control: private`.
4. While it is off, catalog responses are `Cache-Control: public, max-age=60` (P5-V10).
5. The `prelaunch_on` fixture sets the row for one test.

## Consequences

- `spec/schema.sql` gains `site_setting`. T5.7 adds the model, the migration (P2-V01 compares migrations to the schema), the admin page and the catalog check.
- The storefront learns the mode from the `503` body (T12.15). Going live is a bulk publish plus turning the flag off in the admin (T22.5).
- Because the flag is off by default, the production deploy must turn it on before the catalog is published.
- Changing the location later (for example to an environment variable) touches the table, the admin page and the `prelaunch_on` fixture only.

## Source

G32; OA-41 (2026-10-25); T5.7, T12.15, P5-V15, P12-V28, P15-V16, P22-V21, REQ-062, R-19.
