# ADR-0063: The composables coverage returns to 100% through unit tests

## Status

accepted (2026-11-05)

## Context

The composables coverage ratchet failed in `make test-all`: composables stood at 69.23% against a baseline of 100% because `usePageSeo.ts` had no unit test and `useServerFailure.ts` was at 50% (G54). The server path of `failOnServer` could not be tested, because Vitest runs as the client and `import.meta.server` is false there.

## Decision

Add unit tests for `usePageSeo` and for the server path of `failOnServer`, until composables are back at 100%. `failOnServer` takes the server flag as a defaulted parameter (`server = import.meta.server`), so a test can take the server path; callers do not change. Alternative not taken: lowering the baseline, which the ratchet forbids.

## Consequences

The ratchet holds at 100% for composables. A new composable needs its tests in the same task. Removing the parameter would put the server path out of reach of unit tests again.

## Source

G54; OA-79.
