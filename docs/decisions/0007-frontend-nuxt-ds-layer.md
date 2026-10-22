# ADR-0007: Frontend: Nuxt 4 SSR on the Design System layer

## Status

accepted (2026-10-21)

## Context

The storefront needs server rendering for search engines and first paint. The plan asked for plain Nuxt UI with its own `main.css` and npm. The Design System now exists and owns the UI (C-01, C-02), brings Nuxt UI 4.11.2 and Tailwind 4.3.3, and verifies its install path with pnpm (C-11). The plan also compared a Vue SPA, which gives up server rendering, and Django templates, which split the UI from the Design System's Vue components.

## Decision

1. `web/` is Nuxt 4 with server-side rendering, extending the layer `@vinsmokemau/cup-noobles-nuxt`.
2. The package manager is pnpm. Nuxt is pinned to the version of the Design System consumer fixture (4.5.2).
3. Nuxt UI arrives only through the layer. The storefront adds no visual styling of its own (CR-26, CR-27).

## Consequences

- The look comes from the Design System at a pinned version (ADR-0022).
- SSR needs a route from the Nuxt server to Django in production (G18).
- A missing component is a DSR item, not a local workaround.

## Source

Plan 3.3; C-01, C-02, C-11; OA-12.
