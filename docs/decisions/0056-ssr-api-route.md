# ADR-0056: Server rendering reaches Django through a Nitro proxy rule

## Status

accepted (2026-11-02)

## Context

The storefront calls the API at the relative path `/api` (ADR-0010). In the browser, Caddy routes that path to Django. During server rendering there is no browser to resolve it, and `nitro.devProxy` exists only in development, so a production build had no route from the server render to Django (G18).

Alternative: a second, public API origin that both the browser and the server call. It breaks the same-origin rule of ADR-0010 and needs CORS and a second cookie scope.

## Decision

Nitro `routeRules` proxy `/api/**` to a server-only API target, read from `NUXT_API_SERVER_TARGET` at build time and never exposed to the browser. Part A defaults to `http://api:8000`; Phase 20 sets the production value. T12.1 built it, and P12-V01 proves it.

## Consequences

Server-rendered pages and the browser use the same `/api` path. The target is a deploy setting (SPEC.md §4.7). Because Nitro bakes `routeRules` at build time, changing the target means a rebuild. P12-V25 checks the failure path: an unreachable target renders the error page.

## Source

G18; OA-72; OA-67 (the `NUXT_API_SERVER_TARGET` row in §4.7).
