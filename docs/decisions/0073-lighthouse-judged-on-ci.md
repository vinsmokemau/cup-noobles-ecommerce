# ADR-0073: The Lighthouse budget is judged on CI only

## Status

accepted (2026-11-13)

## Context

The home page scores close to its Lighthouse performance budget of 0.85 on the owner's machine
(Docker with 8 GB). Across five full local runs of `make test-all` the score was 0.82 and 0.84 in
two of them, so the command does not pass twice in a row there (G64, found while closing T13.16).
T13.16 changes no web code, and it is not known whether the cause is the Phase 13 home page or
measurement noise on a local machine.

Alternatives considered:

- Find what weighs on the home page and fix it in a storefront task: open-ended, and a local
  score still varies.
- Change the budget: a business value that only the owner sets.

## Decision

The budget stays 0.85. It is judged on CI, where the machine is steady. Outside CI the Lighthouse
step of `make test-all` reports a score below budget as a warning and does not fail. In CI it
fails as before. G64 resolves when the CI Lighthouse run of the T13.16 commit scores 0.85 or
higher.

## Consequences

- A local `make test-all` can be green with a Lighthouse warning; CI is the gate.
- A real regression is caught by CI, not by the local run.
- Changing it later touches only the `lighthouse` target of the Makefile.

## Source

OA-91; G64 (SPEC.md §2.4); T12.12; P13-V30.
