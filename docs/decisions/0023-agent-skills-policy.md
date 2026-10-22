# ADR-0023: Agent skills policy

## Status

accepted (2026-10-21)

## Context

Third-party agent plugins, hooks and always-on rule sets can add network traffic, telemetry, and rules that contradict this spec. SPEC.md §0.5 lists the tools considered (caveman, ponytail, playwright-skill, graphify, taste-skill, awesome-design-md) and why each was not adopted. The owner accepted those verdicts (OA-13).

## Decision

Sessions use only the skills `task`, `review`, `ui-review` and `decide`, plus Claude's built-in tools. No third-party plugin, hook, MCP server or always-on rule set is added. A third-party skill is adopted only by copying it into `.claude/skills/<name>/`, pinned to its source commit, with its license, adapted to this spec, mirrored into `.agents/skills/<name>/`, and through an amendment. Nothing a skill produces counts as proof unless it is a named test.

## Consequences

- The agent behavior is reproducible and auditable from the repository.
- A useful outside tool needs an amendment before use.

## Source

OA-13; SPEC.md §0.5.
