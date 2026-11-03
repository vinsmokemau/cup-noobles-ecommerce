# ADR-0058: The sold-out text of a variant option is in its visible label

## Status

accepted (2026-11-02)

## Context

`VariantSelector` marks a sold-out option with "· Agotado", but the text reaches only the radio's accessible name, which Nuxt UI sets once at mount. After the visitor changes a choice, the name goes stale: an available option can still be announced as sold out. The visible label never shows the text (G52).

Alternative: ask the Design System for a sold-out state on its choice control first. It is slower and may be unnecessary if the radio group's label slot can carry the text.

## Decision

Show "Agotado" in the visible label of a sold-out option through the radio group's label slot, and keep each option's accessible name correct as the choice changes. If the slot cannot do this, register a DS request for a sold-out state on the choice control and report it to the owner. Task T12.21 builds it, and P12-V10 covers it.

## Consequences

The sold-out state no longer depends on color or on a name set once. If a DS request is needed, T12.21 stops until the DS releases it. No schema or API change.

## Source

G52; OA-74.
