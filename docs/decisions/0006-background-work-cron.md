# ADR-0006: Background work: cron and management commands

## Status

accepted (2026-10-21)

## Context

The store has scheduled work: expiring reservations, reconciling payments, retrying webhooks, sending the email outbox and checking integrity (§4.8). The plan compared Celery with Redis, which adds a broker, a worker process and their operations, for a store of launch scale (A4). Cron-driven management commands are plain, idempotent and testable.

## Decision

Background work is Django management commands run by a scheduler from `infra/crontab` (§4.8). There is no Celery and no Redis (§1.3).

## Consequences

- Fewer moving parts in Part A and in production.
- Work is polled, not pushed, so latency is bounded by the schedule.
- Production needs a process that runs the schedule (G23).
- Moving to a queue later changes the entry points, not the services.

## Source

Plan 3.2; §4.8; G23.
