# ADR-0039: The full SEPOMEX dataset is a launch requirement

## Status

accepted (2026-10-25)

## Context

G30: T6.6 called the SEPOMEX postal-code data optional, while the Phase 22 launch checklist (T22.3, P22-V14) requires it. The sample fixture (about 40 codes) is enough for Part A; a shopper whose code is missing falls back to free text (P13-V06).

## Decision

1. The full SEPOMEX dataset is a launch requirement. T22.3 loads it with `manage.py load_postal_codes` and `POSTAL_CODE_DATASET=sepomex`, and P22-V14 checks it by hand.
2. The sample stays for Part A and for tests.

## Consequences

- T6.6 needs no code change. The loader reads a CSV with the columns `postal_code,neighborhood,municipality,state_code`; the real SEPOMEX download has a different layout, so T22.3 must convert it first (the spec does not define the conversion yet).
- `prod.py` still accepts `POSTAL_CODE_DATASET=sample` until Phase 22 makes `sepomex` mandatory (OA-16).

## Source

G30; OA-43 (2026-10-25); T6.6, T22.3, P22-V14, P13-V06.
