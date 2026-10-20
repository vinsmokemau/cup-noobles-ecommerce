---
name: task
description: Execute exactly one task from SPEC.md by its ID, following the SDD execution protocol and the task and phase-close reports.
argument-hint: "[task-id, e.g. T4.1]"
disable-model-invocation: true
---

Execute task $ARGUMENTS from SPEC.md. Do only this task.

## 1. Load context

- Read SPEC.md §0 and §2.
- Find the task in §6: the line `- [ ] **$ARGUMENTS — …**`, its fields, and its body up to the next task line or heading. Read the phase's deliverable and any normative subsection the task names (8.A, 9.A, 10.A…).
- Read every section in the task's Context field, every Verify row listed in its Verifies field (in its phase's Verify table), and the §3 requirements in its REQs field.

## 2. Check the gate

Stop and report if any check fails.

- The task exists, is not struck through (absorbed), and is not already `[x]`.
- Its release is the release in progress (§1.2): Release 1 unless the owner has said otherwise. An `R2` task stops here.
- Every item under "Depends on" is met:
  - each task named is `[x]`;
  - "Phase N closed" means that phase's task marked `Gate: phase-close` is `[x]`;
  - a DSR item is released in a DS version the storefront pins (ask the owner if unsure);
  - an S item is done (ask the owner).
- Open items:
  - "(blocking)" stops the task unless the owner confirms the item is resolved;
  - "(tests xfail until decided)" doesn't stop it: write those tests against the gap's proposed resolution with `xfail(strict=True, reason="G#")`;
  - "(stand-in §2.5)" uses the stand-in.
- `git status` shows a clean working tree.
- The last CI run on the current branch is green (`gh run list --limit 1`). If it is red, stop and report it. If `gh` isn't available, ask the owner. Before the first push there is no run; say so.

## 3. Plan

In 5 to 10 lines, state the files you will create or change, the tests you will add (named by Verify ID, §4.6), and how the gate will be proven. Then proceed, unless the plan needs a decision from the owner. In that case, ask and stop.

## 4. Implement

- Follow SPEC.md exactly (§0.1). Never invent business or brand values (CR-45, CR-46).
- Name each test after its Verify ID. Never edit an existing assertion unless the spec now requires it; list any such change in the report (CR-38).
- If the spec is ambiguous or contradicts itself, an ADR or a Design System doc, quote the passages and ask. Do not pick one.
- For steps only the owner can do (GitHub settings, dashboards, accounts, credentials, deploys), list them for the owner. Never fake or skip them.
- Storefront tasks in Phases 12–14: run `/ui-review` on the changed files before the report, and fix or register each finding.
- The phase-close tasks of Phases 4, 8, 9 and 16: run `/review` on the phase's commits before the phase-close report.

## 5. Verify

- Every task: `make test`; `make e2e FILES=<specs>` for the end-to-end specs the task adds or changes; `make check-migrations` if models changed.
- A task marked `Gate: phase-close`: `make test-all` as well, or the green CI run for the closing commit.
- Fill in the task report from §0.2 with evidence, and for a phase-close task the phase-close report too. Report each box as pass or fail.

## 6. Close

- If any box fails, do not mark the task done. Report what failed and stop.
- Otherwise, commit the work as `$ARGUMENTS: <task title>`.
- Then change the task's line in SPEC.md §6 from `- [ ] **$ARGUMENTS — <title>**` to `- [x] **$ARGUMENTS — <title>** (<today's date>, <short SHA of the work commit>)`, and commit that as `$ARGUMENTS: mark done`.
- Do not push.
- Report what changed, the report or reports, any open questions, and the next tasks whose dependencies are now met.
