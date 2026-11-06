---
name: order-tasks
description: Work out the execution order of the tasks of one SPEC.md phase and write it into the phase as an "Execution order" note, with the OA row and the spec version, the way Phases 7 to 13 have it. Use when the owner gives a phase number and asks for its task order, dependencies or execution order, before the phase starts.
argument-hint: "[phase number, e.g. 14]"
disable-model-invocation: true
---

Find the order in which the tasks of Phase $ARGUMENTS must run so that no task needs one that comes after it, then record it in SPEC.md. Task IDs often do not follow the order of work (T13.8 runs first, T13.13 fourth), and running by number is how a task ends up needing work that does not exist yet.

This skill changes spec text only. It never renumbers a task, never moves a task block, and never edits a Verify ID, a REQ or `spec/schema.sql`. The owner's request in chat is the authority for the amendment (SPEC.md §8).

## 1. Load

- Read SPEC.md §0 and §8, and the whole of the phase's section in §6: deliverable, scope line, pages or sub-sections (`N.A`), every task block, and the Verify tables.
- If the phase already has a `**Execution order.**` note, read it and the OA row that added it. Treat the job as a check of that note, and update it only if a task was added, moved or re-scoped since.

## 2. Build the dependency list

For each task, collect what it needs before it can run, from these sources, strongest first:

1. Its `Depends on:` field. A phrase such as "Phase 12 closed" or "the R2 work of Phases 7, 8 and 10" is a dependency on other phases, not on a task of this one.
2. The Verify IDs it owns. A test that uses a helper, endpoint or fixture built by another task (for example "via `/dev/test/orders/`, T13.8") needs that task first, even if `Depends on` does not say it.
3. Its description, when it says it uses, extends or is authorised by another task's output.

Do not treat these as dependencies. A task that merely names a later task ("T13.3 lists the Factura section, built by T11") is leaving a stub or a pointer: say so in the note, as Phase 9's note does. Likewise the "Fixtures and factories introduced" list and the traceability matrix show who owns what, not what must run first.

Separate the tasks by release. `R1` tasks come first. `R2` tasks (their Release field, or an `[R2]` Verify ID) come after all of R1, in their own dependency order. A task with `Gate: phase-close` runs last of its release.

## 3. Sort

Order the tasks so every task comes after everything it depends on. When several tasks could go next, prefer the order they are already listed in, so the note matches the file. Group tasks that are independent chains (for example a cart chain and an endpoint chain) and say that they can run in either order but must both finish before the task that joins them.

Then check, one task at a time, that nothing in its sources (section 2) points to a task later in your order. If something does, fix the order, or if two tasks need each other, stop and ask the owner: that is a conflict in the spec, not a sorting problem.

Also compare your order with the order the tasks are listed in the file. If they differ, that is fine and expected (IDs keep their numbers), but the note must say so. If the listed order itself breaks a dependency, report it: the owner decides whether to reorder the blocks.

## 4. Report before writing

Show the owner, in plain language:

- The order as a numbered table: position, task, depends on, and why it sits there.
- Anything that waits for something outside the phase: a Design System release (DSR items), an open item (G, D) whose tests stay `xfail`, an R2 prerequisite.
- Tasks that mention another task without depending on it.

Then write the note. The owner already asked for it by giving the phase, so no further question is needed unless section 3 found a conflict.

## 5. Write it in SPEC.md

Follow the shape the earlier phases use. Look at Phase 12 and Phase 13 before writing, and copy their form:

1. **The note**, placed after the phase's `**Release 1 scope:**` line (or after the deliverable if there is none):

   ```text
   **Execution order.** Task IDs do not follow the order of work. Run the tasks in the order they are listed below, which is also this one, and each depends only on tasks before it:

   - <Group>: T<n>.a → T<n>.b → ...
   - Phase close: T<n>.x (needs ...)
   - R2, after R1: T<n>.y

   IDs keep their numbers (OA-<k>). <Which task names another without depending on it, and what it leaves as a stub. Which open items keep which tests xfail.>
   ```

   Use short groups with arrows for chains, and state what a joining task needs. Skip the sentence about open items if there are none. If the phase's tasks are already listed in order and the numbers follow it, the note can be one line.
2. **The register row** in §2.6, after the last `OA-` row, mirroring OA-66 and OA-80: date, the question ("Phase N task order: ... Add one, or renumber?"), and the answer "Option A: add the note. Execution order: ... IDs keep their numbers. ... No ADR: cheap to reverse, spec text only."
3. **The version.** Raise the `Spec version` in the header by one minor, and add a row to the change log (§8) after the last one: "Phase N gets an execution-order note, as Phases 7 to M have. No task, Verify ID or schema change." with the OA id and "owner request in chat".
4. If the phase's row in the conversion table (Appendix E, "Tasks | Listed in execution order") exists, leave it as is.

Edit with exact string replacements, keep the file's line endings, and run `git diff --stat SPEC.md` afterwards: only the lines you added and the version number should show. A whole-file diff means the line endings changed; fix that before going on.

## 6. Finish

- Run `make lint` if it exists (markdownlint covers SPEC.md).
- Do not commit unless the owner asks. When they do, the message is `decide: OA-<k> — Phase N execution order`.
- Say what you wrote, the OA id and the new spec version. Do not start any task of the phase.
