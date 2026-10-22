# ADR-0009: API client generated from OpenAPI

## Status

accepted (2026-10-21)

## Context

The owner is weakest on frontend (A10). A hand-written client drifts from the API silently, and the mismatch shows up at runtime. DRF can emit an OpenAPI schema, and a snapshot of it can be diffed in review and in CI.

## Decision

The storefront's API types and client come from the committed OpenAPI snapshot (`openapi.snapshot.yml`), regenerated with `make schema-update` into `web/app/types/api.d.ts`. The client is never written by hand (CR-25). An API change that does not update the snapshot fails the task report's OpenAPI box.

## Consequences

- An API change is visible in the diff of the snapshot and of the generated types.
- Contract tests (schemathesis) can check the API against the same schema.
- Every intentional API change needs a `make schema-update`.

## Source

Plan 3.3 rule 2 and 5.5; CR-25; A10.
