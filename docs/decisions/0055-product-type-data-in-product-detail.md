# ADR-0055: The product detail response carries the type's attribute schema and variant axes

## Status

accepted (2026-11-02)

## Context

`GET /api/catalog/products/{slug}/` returns `product_type` as a code only. The storefront needs the type's `attribute_schema` to label and order the spec table (`AttributeTable`, SPEC.md §4.4), and the product's resolved variant axes to name and order the variant groups (`VariantSelector`). Neither is in the response, so the product page cannot fill the components built in T12.4 (G50).

Alternatives:

- A separate product-types endpoint: a second request on every product page, for data that belongs to the product.
- Titles hardcoded in the storefront: breaks the rule that a new category needs no frontend work (P12-V11) and puts catalog data in code.

## Decision

The product detail response adds two read-only fields, and keeps `product_type` as the code:

- `attribute_schema`: the `properties` of the product type's schema with their `title`.
- `variant_axes`: the resolved axes (`resolve_variant_axes`, so a product's own override wins over its type's).

The OpenAPI snapshot and the generated types are regenerated. Task T12.19 builds it.

## Consequences

The product page needs one request. The storefront names no product type. The response grows by the size of one schema. Removing the fields later breaks the product page, and P12-V04 would catch it.

## Source

G50; OA-69.
