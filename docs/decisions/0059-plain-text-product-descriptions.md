# ADR-0059: Product descriptions are plain text for the first launch

## Status

accepted (2026-11-02)

## Context

`product.description_md` is named as Markdown, but the spec defines no renderer or allowed subset, so the product page showed it as plain paragraphs (G53). Rendering Markdown needs a sanitised renderer and a list of allowed elements; rendering unsanitised catalog text as HTML is unsafe.

Alternative: a sanitised Markdown renderer (paragraphs, lists, emphasis, links). It adds a dependency and a rule to maintain, for formatting the first launch does not need.

## Decision

For the first launch, descriptions are plain text. The product page shows them as paragraphs, split on blank lines, and renders no Markdown or HTML. The column keeps its name, so a renderer can be added later without a schema change.

## Consequences

Catalog authors write plain text; Markdown symbols appear as typed. No new dependency and no HTML from catalog content reaches the page. Adding formatting later is an amendment that picks the renderer and the allowed subset.

## Source

G53; OA-75.
