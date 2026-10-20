<!-- markdownlint-disable-file MD041 -- the PR title is the H1, so the body starts at H2. -->

## Task

<!-- The SPEC.md §6 task ID, for example T4.1, or "decide: <ID>" for a decision. -->

## Task report

<!-- Paste the task report from SPEC.md §0.2, filled in with evidence. -->

## Phase-close report

<!-- Only for a task marked `Gate: phase-close`; otherwise write "n/a". -->

## Spec sync checklist

Tick each item, or write "n/a" and why.

- [ ] `SPEC.md`: the task is ticked `[x]` with its date and commit. Nothing else changed, or the change is an amendment with a §8 row (an ADR or the owner).
- [ ] §2.4: new unknowns are registered; resolved items cite their ADR; no `xfail` remains for a resolved item.
- [ ] No business or brand value was added without a source: §2, an ADR, or the owner (CR-45, CR-46).
- [ ] No internal business data, cost file or secret is in the diff (CR-48 to CR-50).
- [ ] `openapi.snapshot.yml` and the generated types changed together, through `make schema-update`.
- [ ] README, RUNBOOK and SPEC.md §4.7 are updated if commands, environment variables or operations changed.
- [ ] `CLAUDE.md` and `AGENTS.md`, and `.claude/skills/` and `.agents/skills/`, still match.
- [ ] `make test` passes locally; for a phase-close task, `make test-all` too.
