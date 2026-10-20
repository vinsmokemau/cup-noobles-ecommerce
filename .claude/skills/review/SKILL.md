---
name: review
description: Review a change or a phase like the senior developer who gets paged when it breaks — correctness, safety, load, tests, speed, needless code — with SPEC.md as the authority. Reports findings only. Use for /review, "review this", "review Phase 8", and before the phase-close report of Phases 4, 8, 9 and 16.
---

<!-- Adapted from ponytail-review (github.com/DietrichGebert/ponytail, commit 09c434a), MIT License; see LICENSE in this folder. Changes: SPEC.md takes precedence; the Cup Noobles rules and expected load; the spec's tests and coverage gates replace "one good test"; findings only. -->

Review a change like the senior developer who will be paged when it breaks. Order of importance: correct, safe, holds under load, tested, fast, lean. This is a report the owner asked for, so give it in full. Change no code.

## 0. The spec decides

- SPEC.md is the contract. Read §0, §2, and the tasks and Verify rows the change belongs to.
- A finding that would contradict SPEC.md, an ADR or a Design System doc is not a finding. Report it as a question for the owner, quoting the passages.
- Never propose removing what the spec requires: the adapters and the registry (§4.3, including the manual `InvoiceProvider`), validation, database constraints, a Verify test, or coverage.

## 1. Understand first

- Review what the owner names: uncommitted or staged changes, a branch, a commit range, or a phase. A phase means the commits of its tasks (`git log --grep "^T8\."` for Phase 8). Nothing named: the uncommitted changes, or the last commit if there are none.
- Read the diff, then the code it touches: callers of every changed function, the functions it calls, the tests.
- Trace the real flow: where data comes in, what is stored, what goes out.
- A change can break code it does not touch. When a signature, return value or behavior changes, grep every caller.
- The expected load is A4 (SPEC.md §2.3): under ~500 orders a month, ~5,000 SKUs and ~50k pageviews, on one small server, with webhooks, scheduled jobs and the admin acting at the same time. Judge scale against that.

## 2. Look for

1. **Bug:** wrong result, crash, missed edge case (empty, zero, last item, rounding, time zones), a caller broken by the change, a fix applied in one caller while the shared function stays broken.
2. **Risk:** security holes (injection, weak randomness, secrets, missing checks on input from customers or webhooks), data loss (errors swallowed, writes in the wrong order, no transaction), and anything that must not be in a public repository (CR-48 to CR-50).
3. **A broken spec rule:** money not in integer centavos (CR-01); a total computed outside `compute_totals` (CR-02); an order state set outside `apply_event` (CR-09); `on_hand` changed without a ledger row or without `SELECT … FOR UPDATE` (CR-05, CR-07); a webhook amount or status trusted without a fetch (CR-12); vendor code outside its adapter (CR-19); a business or brand value with no source (CR-45, CR-46); visual styling in the storefront (CR-27).
4. **Scale:** fine for one user, wrong under concurrency: check-then-write races, the same work done by every process, a query per item, lists that only grow, per-process state that must be shared.
5. **Missing or weak test:** a Verify ID of the task with no test; a test whose assertion doesn't match its Verify row; risky new logic (a branch, money, stock, order state, security, a data write, a bug fix) with no test that fails when it breaks; an `xfail` whose reason names no gap.
6. **Speed:** big slowdowns are problems. Small wins, such as work repeated in a loop, are suggestions.
7. **Lean:** code that should not exist or should be smaller.
   - delete: dead code, unused options, features the spec doesn't ask for
   - reuse: the repository already has this helper (name the path)
   - standard library or platform: it already does this; a new dependency for a few lines
   - merge: near-copies that must change together
   - split: one function doing several unrelated jobs. Split by job, never by line count.

## 3. Check before you report

- Every finding needs a concrete case: "this input or situation leads to this wrong result". No case, no finding.
- Re-read the lines and confirm: the caller exists, the value can really be empty, the code really is unused.
- Propose the smallest fix that works. Prefer fixes that delete code. Never add layers, frameworks or settings the problem does not need.
- No style taste, no "consider", no vague worries.

## 4. Output

Very simple English: short sentences, everyday words. Explain a technical term the first time you use it. The reader may never have seen this code.

Start with `What this change does:` in two or three sentences.

Then the findings in three groups, skipping empty groups:

- **Must fix:** a bug, a security hole, data loss, a broken spec rule, or a break at the expected load.
- **Should fix:** risky code without a test, real slowness, duplication, a function that mixes jobs, code that should not exist.
- **Nice to have:** small speed-ups, shorter forms.

Number findings across all groups, so the owner can say "fix 2 and 5". Every finding names the file and lines and has four parts, each one or two short sentences:

1. **Orders numbered in the wrong year** (`api/apps/orders/numbering.py:L12-18`)
   - **What this is:** The order number carries the year the order was placed.
   - **Problem:** It takes the year from the server clock in UTC. An order placed at 23:30 on 31 December in Mexico City gets next year's number.
   - **Fix:** Take the date in the store timezone (G5). One line; nothing else changes.
   - **If we skip it:** A few orders a year carry the wrong year, and the sequence has a gap.

Then, if there are any, `Questions for the owner:` — each conflict with the spec, quoting the passages.

End with:

- `Verdict: Ship.` or `Verdict: fix 1 and 3 first.`
- `Not checked:` one line, if something mattered and you could not check it.

Nothing found: `What this change does:`, then `Looks good. Ship.` and one line on what you checked.

A finding the current task doesn't fix becomes a new task or a register item, through the owner (SPEC.md §8). This skill lists findings and changes no code.
