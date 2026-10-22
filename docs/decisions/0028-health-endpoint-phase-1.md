# ADR-0028: Health endpoint in Phase 1

## Status

accepted (2026-10-21)

## Context

P1-V11 and P1-V17 verify `/api/health/` in Phase 1, but the plan specified the endpoint only in Phase 20 (20.4). The owner chose the proposed resolution of G1.

## Decision

1. T1.16 builds `GET /api/health/` in Phase 1. It runs `SELECT 1` and returns 200 with `{"db": "ok"}`, or 503 when the database is unreachable.
2. T20.4 stays absorbed by T1.16 (the endpoint) and T20.3 (the Lightsail health-check configuration, path `/api/health/`).
3. P1-V11 and P1-V17 are ordinary passing tests, with no `xfail`.

## Consequences

- The endpoint exists before the deployment work, and Phase 20 only configures the health check.
- Changing the path or the response body later touches P1-V11, P1-V17, P20-V01 and P20-V03.

## Source

G1, OA-20.
