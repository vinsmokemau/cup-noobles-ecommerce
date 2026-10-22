# ADR-0021: Public repository

## Status

accepted (2026-10-21)

## Context

The plan wanted a private repository with branch protection. On GitHub Free, branch protection is available only to public repositories (C-12, DS:OD-14). The alternative was a private repository on a paid plan. The owner chose a public repository, created by the owner (OA-10).

## Decision

The repository is public on GitHub Free. Internal business data never enters it: the execution guide, budgets, suppliers, margins, costs, sales targets, catalog files with costs, and secrets (CR-48, CR-49, CR-50). The execution guide is cited by ID only.

## Consequences

- Branch protection and free CI minutes are available.
- Every commit is public, so review must catch internal data before it lands.
- Making the repository private later is a settings change, but history already published stays exposed.

## Source

OA-10; C-12; A18; CR-48 to CR-50.
