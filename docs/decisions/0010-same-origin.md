# ADR-0010: One origin through Caddy; session auth

## Status

accepted (2026-10-21)

## Context

With the storefront and the API on separate domains, the browser needs CORS and the API needs token authentication (JWT) with refresh logic, each a source of security mistakes and client code. The plan compared separate domains with CORS and JWT against a single origin.

## Decision

Caddy fronts both apps on one origin: `/api/*` goes to Django and everything else to Nuxt (§4.1). Authentication is a plain Django session cookie, with CSRF enforced. There is no CORS configuration and no JWT.

## Consequences

- No token storage, refresh or CORS to maintain.
- The proxy is part of the runtime in Part A and Part B.
- Server rendering must reach Django through a server-side route (G18).
- Serving the API from another domain later would need CORS and a new auth scheme.

## Source

Plan §2; SPEC.md §4.1.
