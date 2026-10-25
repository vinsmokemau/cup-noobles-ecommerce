# ADR-0040: The guest order lookup is a POST with a JSON body

## Status

accepted (2026-10-25)

## Context

G35: the guest lookup was specified as `GET …/lookup/?number=&email=`, which puts the customer's email in the URL, where proxies, the CDN and error logs record it.

## Decision

1. The lookup is `POST /api/orders/lookup/` with the JSON body `{number, email}`.
2. It stays limited to 5 requests per hour per IP, and a wrong email and a missing order return the same 404 body.
3. The `/rastrear` page (T14.6) submits a `POST`.

## Consequences

- P6-V14 and P6-V18 are plain tests, with no `xfail`. No `xfail` marker existed yet, because T6.7b is not built.
- Changing back to `GET` would touch the endpoint, P6-V14, P6-V18, the OpenAPI snapshot and the `/rastrear` form.

## Source

G35; OA-44 (2026-10-25); T6.7b, T14.6, P6-V14, P6-V18.
