# ADR-0016: Mock-first integration adapters

## Status

accepted (2026-10-21)

## Context

Part A has to prove the business logic with no accounts, credentials or bills (A13). The plan compared building against real sandboxes from the start with building against mocks, and compared keeping mock state in the application database with keeping it outside. Mock tables in the app database pollute the schema and hide the boundary. A mock easier than the real provider hides bugs until Part B (A14).

## Decision

1. Every third-party service sits behind an interface in `apps/core/providers.py`, selected by one environment variable each (CR-18, CR-21).
2. Only the adapter module imports a vendor SDK or an HTTP client for a vendor (CR-19). Vendor SDKs live in the optional `integrations` dependency group (CR-23).
3. Mocks are the default in dev and test; `prod.py` refuses any mock (CR-20). An unknown provider value is a startup error.
4. Mock state lives outside the application database, under `var/mocks/`.
5. Each boundary has one contract suite that runs against the mock and, in Part B, against the real sandbox (CR-22).

## Consequences

- Part B swaps environment variables and adds adapters, not domain code.
- Contract suites are the price: each boundary needs one.
- Architecture tests (`test_vendor_imports`, `test_provider_selection`) enforce the layering.

## Source

Plan §5, 9.9 and 9.13; CR-18 to CR-23; A13, A14.
