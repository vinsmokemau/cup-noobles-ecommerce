# ADR-0017: Test discipline

## Status

accepted (2026-10-21)

## Context

The business rules involve money, stock and payments, where a silent regression is costly, and there is one maintainer. The plan compared SQLite with PostgreSQL for tests, fixed coverage thresholds with a ratchet, and manual checklists with traced tests. SQLite behaves differently on locks, constraints and JSONB. A fixed threshold either blocks progress or lets coverage fall. A manual checklist does not run on every push.

## Decision

1. Tests run on PostgreSQL only; SQLite aborts the run (CR-40).
2. Coverage is measured by branch, with gates and a ratchet that never lets a scope decrease (CR-44).
3. Every Verify ID has a named test, and the traceability check proves it for the release in progress.
4. Earlier tests are not edited to make new work pass (CR-38). No silent skips (CR-39). No `sleep()` in tests (CR-43).
5. Part A makes no outbound connection, and an offline clean-clone run proves it (CR-41).

## Consequences

- A task is not done until its tests pass, and a phase is not done until `make test-all` passes (CR-37).
- The suite is slower than a SQLite one; the `slow` marker and the per-task light suite offset that (ADR-0018).

## Source

Plan §6, §6.A, §6.B; CR-37 to CR-44.
