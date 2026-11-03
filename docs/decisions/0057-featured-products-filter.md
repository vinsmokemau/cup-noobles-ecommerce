# ADR-0057: The product list takes a `featured` filter

## Status

accepted (2026-11-02)

## Context

ADR-0030 added `product.is_featured` and `featured_position` for the home page (G28). No public API exposed them: the product list had no `featured` filter, the card carried no flag, and there was no featured endpoint, so the home page could not list featured products (G51).

Alternatives:

- A separate `/api/catalog/featured/` endpoint: the same data, plus a new route to document, cache and test.
- A separate task before T12.16: the same change, one task later, with the home page blocked in between.

## Decision

`GET /api/catalog/products/` accepts `featured=true`. It returns active featured products ordered by `featured_position`, then `id`, with the same cursor pagination and cache headers as the rest of the list. Without the parameter, or with `featured=false`, the list is unchanged. T12.16 builds it, with the OpenAPI snapshot and types regenerated, an API test, and the E2E catalog seed.

## Consequences

The home page needs one list request. The facets endpoint accepts the same parameter, because it shares the query serializer. Removing the filter later breaks the home page, and P12-V13 would catch it.

## Source

G51; OA-73; G28; ADR-0030.
