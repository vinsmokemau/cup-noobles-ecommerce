---
name: decide
description: Record the owner's answer to an open item in SPEC.md §2.4 (S, D, G, C or DSR): the owner answer, the ADR, the register, the xfail markers and the spec version.
argument-hint: "[item ID, e.g. G3 or D14] [the owner's answer, if given]"
disable-model-invocation: true
---

Record the owner's decision on $ARGUMENTS. The answer must come from the owner in this session; never infer it.

## 1. Load

- Read SPEC.md §0, §2 (the item's row in §2.4, and §2.5 and §2.6), §7.2 and §8.
- Find every place the item is cited: `grep -rn "<ID>"` across SPEC.md, `spec/schema.sql`, the code and the tests.

## 2. Get the answer

- If the owner hasn't answered yet, present the options: the item's proposed resolution, labelled as a proposal, and the real alternatives. For each, say what it changes (schema, tasks, tests, settings, cost to change later). Give a recommendation and ask for a one-letter reply. For a visual choice, publish a comparison page first (CLAUDE.md, "Owner decisions"). Then stop and wait.
- Restate the decision in one sentence, and get the owner's confirmation before recording it.

## 3. Record

1. Add a row to §2.6: the next OA ID, today's date, the question, and the answer.
2. Write `docs/decisions/NNNN-<slug>.md` from `0000-adr-template.md`, with status `accepted`, citing the OA ID and the item. Add it to `docs/decisions/README.md` and to SPEC.md Appendix B.
3. Update the item's row in §2.4: `Resolved (ADR-NNNN)` for a gap, conflict, signup or DS request that is done; `Decided (ADR-NNNN)` for a business decision whose value is applied later. When a decision replaces a §2.5 stand-in, update §2.5 too.
4. Apply what the decision changes in the spec: the resolution into the affected task bodies and Verify rows; `spec/schema.sql` if the schema changes; §4.7 if it adds a setting; §7.2 if it was listed there. Keep every ID stable; strike through what is removed (§8).
5. Remove the `xfail` markers whose reason cites the item, so those tests must pass. If a test was written against a proposal the owner rejected, rewrite its assertion to the decision and say so in the report.
6. Bump the spec version and add a §8 row: what changed, with the OA and ADR references.
7. If `CLAUDE.md` or a skill changes, change its mirror in the same commit.

## 4. Verify and commit

- Run `make test`; the register check is part of it.
- A test may now fail because the code predates the decision. That is expected: list each failing test and the task that will fix it. If no task does, propose one as part of this amendment, and ask the owner whether to fix it now or in its phase.
- Commit as `decide: <ID> — <short decision>`. Do not push.
- Report the decision, every file changed, and any follow-up task.
