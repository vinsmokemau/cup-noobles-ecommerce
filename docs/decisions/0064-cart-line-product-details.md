# ADR-0064: Cart lines carry the product name and options

## Status

accepted (2026-11-05)

## Context

The cart page (T13.13) lists `CartLine` rows, but the cart response has no product name or variant options. Every row is titled "Producto", so a customer with two variants of one product cannot tell the rows apart (G56).

## Decision

Each line of the `Cart` response gains `product_name` and `options`, taken from the rows the cart already reads for the price. `CartLine` shows them. No image is added. The work is a new task, T13.15, after T13.13 and before T13.5, with P13-V28 (API) and P13-V29 (E2E). Alternative not taken: the storefront fetching each product by variant, which needs a new endpoint and one request per line.

## Consequences

The OpenAPI snapshot and the generated types change in T13.15 (`make schema-update`). A product that is archived after it was added still shows its name in the cart. Adding an image later is a separate change.

## Source

G56; OA-82.
