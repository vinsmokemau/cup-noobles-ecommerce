# ADR-0008: Client state: server state only

## Status

accepted (2026-10-21)

## Context

A client-side store such as Pinia duplicates data the server already owns (cart, session, orders) and invites stale prices and drift. The cart lives in the database (ADR-0011) and the client computes no price (CR-02).

## Decision

No Pinia (CR-24). Cart and session state are server state fetched through the API; ephemeral UI state uses `ref`. Every request goes through `useApi` (CR-29).

## Consequences

- One source of truth; pages refetch instead of syncing.
- A little more network traffic than a client cache.
- Adding a client store later reverses CR-24 and needs an amendment.

## Source

Plan 3.3 rule 1; CR-24.
