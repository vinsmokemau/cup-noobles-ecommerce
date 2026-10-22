# ADR-0025: Brand assets from the Design System

## Status

accepted (2026-10-21)

## Context

D11 asked for the logo, colors and photography standards. The Design System already defines them, and a storefront that supplied its own would fork the brand. The alternative was Nuxt UI's defaults, which are not the brand.

## Decision

All brand assets come from the Design System: logos from DS:ADR-0016, icons from DS:ADR-0012, focus from DS:ADR-0009, photography from DS:ADR-0056 and DS:ADR-0057, and colors from DS:BR-01 to DS:BR-03. D11 is resolved by this reference. The storefront invents none (CR-46).

## Consequences

- No brand work in this repository.
- Gaps become DSR items, for example the raster email logo (DSR-05) and the photo rule for product packaging (DSR-07, C-10).

## Source

D11; CR-46.
