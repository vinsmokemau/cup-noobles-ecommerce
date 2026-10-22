# ADR-0018: Per-task gate and phase-close gate

## Status

accepted (2026-10-21)

## Context

The plan ran the whole suite on every task. The owner wants a light suite per task and the full suite per phase and in CI (C-07, OA-03).

## Decision

1. Every task runs `make test`, plus `make e2e FILES=…` for the end-to-end specs it adds or changes, and `make check-migrations` when models change.
2. The task marked `Gate: phase-close` also runs `make test-all`, or shows the green CI run of the closing commit.
3. CI runs `make test-all` on every push and pull request.
4. The next phase starts only after its phase-close report is complete.

## Consequences

- Tasks stay fast; slow regressions surface at phase close or in CI at the latest.
- The two reports of SPEC.md §0.2 are the evidence.

## Source

OA-03; C-07; CR-37.
