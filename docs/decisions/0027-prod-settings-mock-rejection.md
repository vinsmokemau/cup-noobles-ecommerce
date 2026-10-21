# ADR-0027: Which values `prod.py` rejects, and the installed apps

## Status

accepted (2026-10-20)

## Context

T1.3 requires `prod.py` to reject mock values at startup (CR-20, REQ-040), but §4.3 does not say which provider values are mocks. It also leaves open which apps `INSTALLED_APPS` holds before the apps that need them exist. The owner had no strong opinion on either and accepted Claude's suggestion.

## Decision

1. `prod.py` rejects exactly `PAYMENT_PROVIDER=mock`, `CARRIER_PROVIDER=mock` and `EMAIL_PROVIDER=file` with `ImproperlyConfigured`. `MEDIA_STORAGE=local`, `POSTAL_CODE_DATASET=sample` and `ERROR_TRACKING=off` stay accepted until Phases 18, 22 and 21 give them real values. The Phase 22 launch checklist makes them mandatory. `INVOICE_PROVIDER=manual` is not a mock (§4.3).
2. `INSTALLED_APPS` stays minimal: Django's contrib apps and DRF. Each later task adds its own app together with its tests.

## Consequences

- Production can start before Phases 18, 21 and 22 exist, but the launch checklist must check the three accepted stand-ins.
- Adding a mock-valued switch to the rejected set is an amendment to this ADR.
- P1-V14 covers the three rejected switches only.

## Source

OA-16, OA-17, T1.3.
