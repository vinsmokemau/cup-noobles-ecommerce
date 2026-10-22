# ADR-0024: Price format

## Status

accepted (2026-10-21)

## Context

Plan 12.4 formats prices as `$1,234.00 MXN`, while plan 12.6 gives the `Intl` output with no suffix (G19, C-08). The Design System's `formatting.md` decides the format for every consuming app.

## Decision

Money is formatted only by `formatMXN` and `PriceDisplay`, using `Intl.NumberFormat('es-MX')` with the currency code passed in. The storefront adds no symbol by hand and no suffix (CR-30). The alternative `$1,234.00 MXN` is rejected.

## Consequences

- One formatter, one output, matching the Design System.
- Money stays integer centavos everywhere else (CR-01); formatting happens only at display.
- P12-V09 checks the format.

## Source

G19, C-08; DS:formatting.md; CR-30.
