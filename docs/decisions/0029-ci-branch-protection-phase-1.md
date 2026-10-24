# ADR-0029: CI and branch protection in Phase 1

## Status

accepted (2026-10-23)

## Context

The plan verified CI and branch protection only in Phase 20, though every Part A task relies on them. G29 proposed checking both in Phase 1, with branch protection as a `[manual]` item. The owner chose the proposed resolution and asked for the GitHub settings in force to be written into the record.

GitHub does not enforce branch protection on a private repository on a free plan: the branch-protection API answered 403 ("Upgrade to GitHub Pro or make this repository public"), and a red pull request showed merge state `UNSTABLE`, not `BLOCKED`. The repository was made public on 2026-10-23, after a history audit found no secret, cost, margin, supplier or execution-guide content. Protection then took effect: the same kind of pull request showed `BLOCKED`.

A first rule that required one approving review could not be met by a single maintainer, so the owner set approvals to 0.

## Decision

1. P1-V23 (`[manual]`) is checked in Phase 1: `make test-all` is green on `main` in CI, and a pull request with a deliberately failing test turns the `test-all` check red and cannot be merged. It was checked on 2026-10-23.
2. The settings in force on `main` are:
   - the repository is public;
   - a pull request is required before merging, with 0 required approvals;
   - the `test-all` status check is required, and the branch must be up to date before merging;
   - force-pushes and deletions are not allowed;
   - the rules apply to administrators, so the owner cannot bypass them.
3. Because `main` is protected, every change reaches it through a pull request, including the `T<id>: mark done` commit.
4. If the repository is recreated or made private, these settings are set again before any other task runs.

## Consequences

- A red run cannot reach `main`, so CI is a real gate from Phase 1.
- Every task needs a pull request and a wait for `test-all`, which takes about 13 minutes at this size.
- A private repository on a free plan cannot enforce this. Going private again needs GitHub Pro or an amendment to this ADR.
- Changing the required check name (the job `test-all` in `.github/workflows/ci.yml`) means updating the rule too.

## Source

G29, OA-21. P1-V23.
