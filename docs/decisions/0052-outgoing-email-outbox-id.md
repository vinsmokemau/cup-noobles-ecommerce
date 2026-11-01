# ADR-0052: `OutgoingEmail` carries the outbox id

## Status

accepted (2026-10-31)

## Context

SPEC.md §4.3 and P11-V08 name the file sender's output `<EMAIL_FILE_DIR>/<YYYYmmdd-HHMMSS>-<template>-<outbox id>.html`, but `OutgoingEmail` held no outbox id and `EmailSender.send(message)` takes nothing else, so the sender could not build the name. Alternatives: name files with a random token only (loses the link between a file and its outbox row), or pass the id as a second argument to `send` (breaks the `EmailSender` Protocol for every adapter).

## Decision

1. `OutgoingEmail` gets an optional field `outbox_id: int | None = None`.
2. `send_outbox` (T11.1) sets it from the `email_outbox` row.
3. `FileEmailSender` uses it as the last part of the file name, and a short random token when it is `None`.
4. Resend and SES (Phase 17) ignore it, or send it as a tag.

## Consequences

- The `EmailSender` Protocol is unchanged; the field has a default, so existing constructors keep working.
- P11-V08 asserts the exact file name for `outbox_id=42`.
- Dropping the field later touches `send_outbox` and the file sender only.

## Source

OA-63; SPEC.md §4.3, T11.1, T11.5, P11-V08.
