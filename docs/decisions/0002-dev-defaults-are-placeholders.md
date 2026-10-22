# ADR-0002: Dev defaults are placeholders

## Status

accepted (2026-10-21)

## Context

Part A has to run end to end before the owner has decided shipping rates, payment windows, installment terms, the warehouse address or the launch product types (D4–D7, D14, D16). Waiting on those decisions would block the build. Inventing them silently would put guessed business values into the product (CR-45).

## Decision

1. Where SPEC.md §2.5 lists a stand-in, Part A uses it. Every stand-in is a placeholder, never a business value.
2. Seeded names start with `[PLACEHOLDER]`. Product-type schemas and the CFDI catalog file carry `"$comment": "[PLACEHOLDER]"`.
3. `manage.py check_placeholders` exits non-zero while any placeholder, any `[DEMO]` row, or any D6 or D7 setting at its dev default remains. The Phase 22 launch checklist requires it to exit 0.
4. A value with no stand-in in §2.5 is not invented: it is registered in §2.4 and asked of the owner.

## Consequences

- Part A and its tests run without business decisions.
- Launch is mechanically blocked until every placeholder is replaced.
- Adding a stand-in is an amendment to §2.5.

## Source

SPEC.md §2.5; plan §5.E; CR-45.
