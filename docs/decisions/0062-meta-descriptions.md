# ADR-0062: Meta descriptions of the home, catalog and product pages

## Status

accepted (2026-11-05)

## Context

No page set a meta description, so Lighthouse SEO scored 0.91 to 0.92 against the budget of 0.95 (T12.12, G55). The text of the home and catalog pages is customer-facing copy, and no source in the spec, an ADR or the Design System supplied it. Three options per page were proposed in the Design System voice (BR-05, BR-17) and the owner chose the first of each.

## Decision

- Home (`/`): "Tienda en línea de cultura geek y gamer. Explora el catálogo de Cup Noobles, elige tu favorito y recibe tu pedido en casa."
- Catalog (`/catalogo`): "Explora el catálogo de Cup Noobles: productos de cultura geek y gamer. Filtra por categoría y encuentra el que buscas."
- Product pages: the first paragraph of the product's own description (plain text, ADR-0059), at most 160 characters, cut at a word. A product with no description has no meta description; nothing is invented for it.

## Consequences

"Recibe tu pedido en casa" is true while checkout is delivery only (Release 1). If pickup arrives in Release 2, the home text needs a review. The legal, search and category pages are unchanged: no source supplies their text. Changing a text later is a one-line edit in the page.

## Source

G55; OA-78.
