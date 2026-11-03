# ADR-0060: Text printed on a product may show in its photo

## Status

accepted (2026-11-02)

## Context

The Design System photo standard said "no text inside the image" (DS:ADR-0057). Product packaging photos always carry printed text, so the rule conflicted with the catalog (C-10, DSR-07). The owner decided the scope in the Design System repository on 2026-11-01 (DS:OD-15, DS:ADR-0064, option B), and DS 1.6.0 publishes the wording in its docs.

## Decision

Text printed on the product itself, such as its box or label, may show in a product photo. Text added to a photo is not allowed: banners, price stickers, flashes such as "NEW", watermarks and captions. The title, the tag and the alt text carry the words, so no one needs the picture to read them. "Added text" is judged when a photo is uploaded; no test can detect it. The rest of DS:ADR-0056 and DS:ADR-0057 stands.

## Consequences

Packaging photos can be used as they are. Catalog authors check each upload for added text. The storefront's code does not change. A new task, T12.22, raises the Design System pin to 1.6.0 (docs only).

## Source

C-10; DSR-07; OA-76; DS:ADR-0064.
