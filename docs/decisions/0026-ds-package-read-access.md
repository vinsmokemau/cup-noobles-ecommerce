# ADR-0026: Read access to the Design System packages

## Status

accepted (2026-10-20)

## Context

The three Design System packages (`@vinsmokemau/cup-noobles-tokens`, `-nuxt` and `-email`) are private on GitHub Packages (DS:OD-03), so every install needs a token. T1.5 cannot install them until this repository has read access (S8, risk R-12).

## Decision

The owner granted this repository read access to the three packages. Local installs use a classic personal access token with `read:packages` in the user-level `~/.npmrc`; the token never enters the repository or an image layer (CR-50, §4.5).

## Consequences

- T1.5 is no longer blocked by S8.
- CI reads the packages through `NODE_AUTH_TOKEN` (§4.7); T1.9 wires that.
- Image builds that install the packages are checked from a clean clone in P15-V14.

## Source

OA-15, S8.
