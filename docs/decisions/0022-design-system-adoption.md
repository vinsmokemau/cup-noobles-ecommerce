# ADR-0022: Design System adoption

## Status

accepted (2026-10-21)

## Context

The Cup Noobles Design System was finished and evaluated before this spec (OA-05). It owns components, tokens, fonts, icons and image rules, and forbids visual styling in a consuming app (C-02, DS:OD-11). The storefront needs some parts the Design System lacks (C-03). The owner chose that the Design System adds them first, as minor releases (OA-09). The alternative was styling in the storefront, which splits the brand across two repositories.

## Decision

1. The storefront consumes the layer and the email package at an exact version, currently `1.0.1` (A17). Raising the pin is its own task.
2. The Design System repository is read-only from here. A missing part is a DSR item in §2.4, built and released there.
3. Commerce components are built in the storefront from Design System parts (DS:OD-01).
4. Brand values come only from the Design System (CR-46).

## Consequences

- One source for the brand.
- The storefront waits on DS releases for DSR items.
- A Design System upgrade is a task of its own.

## Source

OA-05, OA-09, OA-12, OA-19; DS:OD-01, DS:OD-11; CR-26, CR-27, CR-46.
