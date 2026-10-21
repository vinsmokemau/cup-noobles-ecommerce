# Cup Noobles E-commerce

This repository is built with Spec-Driven Development. `SPEC.md` and `spec/schema.sql` are the contract: code is built from them, never the other way around.

## How work arrives

- Work comes as exactly one task from SPEC.md §6, through `/task <id>` (for example `/task T1.1`).
- Do one task per session. Never start the next task, even if it looks small.
- Before changing anything, read SPEC.md §0 (execution protocol, reports, commands, skills) and §2 (rules, conflicts, assumptions, open items), then the task's Context field.
- Only tasks of the release in progress are done (Release 1 unless the owner says otherwise). An `R2` task or an `[R2]` Verify ID waits.

## Hard rules

- Never invent business values: prices, rates, payment windows, hold periods, purchase limits, policy or legal text, fiscal data, supplier data. Never invent brand values: colors, type, spacing, shape, effects, icons, logos, motifs or imagery come only from the Design System. Valid sources are SPEC.md §2, an ADR in `docs/decisions/`, or the owner in chat. Anything else is registered in §2.4; Part A uses a stand-in only where §2.5 lists one.
- Money is integer centavos of MXN. Order state changes only through `apply_event`. Physical stock changes only through the inventory services, with a ledger row (SPEC.md §2.1).
- If SPEC.md, an ADR and a Design System doc disagree, stop. Quote the passages and ask the owner.
- Only change SPEC.md to tick the finished task's checkbox. Any other change is an amendment: it goes through `/decide` or the owner directly (SPEC.md §8).
- Never edit an existing test's assertion to make new work pass. The only allowed change is one the spec now requires, listed in the task report.
- The Design System repository is read-only from here. A missing part is a DSR item in §2.4, built in the DS repository.
- This repository is public. Never commit the owner's execution guide, budgets, suppliers, margins, costs or sales targets, a catalog file with costs, or a secret.
- Part A makes no outbound connection beyond package installs.
- Never push, deploy, publish, or change GitHub settings or a third-party dashboard unless the task says so and the owner confirms in chat.

## Owner decisions

The owner is not a designer, and is both the developer and the business owner.

- When the owner must decide something (an open item in §2.4, or a question a task raises), present the options in plain language, mark what can be measured as pass or fail, give a recommendation, and ask for a one-letter reply. A design gap's proposed resolution is labelled as a proposal, never applied before the answer.
- For a visual choice, show the options on a comparison page the owner can open, built with the real Design System components and es-MX copy. In Claude Code, publish it as a private Artifact; other agents write a standalone HTML file outside the repository. Label every value that is not a brand value as an example.
- Record every answer with `/decide`: an owner answer in §2.6, an ADR, the register row, and the spec version.
- `/decide` is for decisions only the owner can make (OA-18): business values, brand and visual choices, and conflicts between SPEC.md, an ADR and a Design System doc. Everything else is the agent's call.
- Technical choices that change no requirement, Verify ID or business value (a version pin, a config layout) need no `/decide`. List each in the task report under "Judgment calls", with the reason and how to undo it.
- A new gap or Design System request is added to §2.4 by the agent and reported to the owner, without an ADR. An ADR is written only for a choice that is costly to reverse: a dependency swap, a data model change, a provider choice.

## Skills and tools

- Use only the skills in SPEC.md §0.5: `task`, `review`, `ui-review` and `decide`. Storefront tasks run `/ui-review`; the phase-close tasks of Phases 4, 8, 9 and 16 run `/review`.
- Do not add third-party plugins, hooks, MCP servers or always-on rule sets. A third-party skill is adopted only by copying it into `.claude/skills/`, pinned, with its license, and through an amendment.

## Instruction mirrors

- `AGENTS.md` is an exact copy of `CLAUDE.md`, and `.agents/skills/` is an exact copy of `.claude/skills/`, for other coding agents.
- Whenever `CLAUDE.md` or a file in `.claude/skills/` changes, apply the same change to its mirror in the same commit.

## Commands

The commands in SPEC.md §0.3 exist from Phase 1 onward. Every task runs `make test`, plus `make e2e FILES=…` for the end-to-end specs it adds or changes. The task marked `Gate: phase-close` also runs `make test-all`. CI runs `make test-all` on every push.

## Language

Code, docs and this spec are in English. Customer-facing copy is Spanish (es-MX) and follows the Design System's voice, microcopy and formatting rules.
