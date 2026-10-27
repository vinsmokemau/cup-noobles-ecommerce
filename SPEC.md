# SPEC.md — Cup Noobles E-commerce

| Field | Value |
|---|---|
| Document type | Requirements specification for Spec-Driven Development (SDD) with Claude Code |
| Spec version | 1.35 |
| Status | Approved for Part A on 2026-10-19 (OA-14). Part B stays draft until P15-V14 passes (local acceptance). |
| Owner | The owner, a single maintainer who is both developer and business owner (A15, OA-04) |
| Repository | Public GitHub repository created by the owner; name pending (S5, OA-10) |
| Design System | `@vinsmokemau/cup-noobles-tokens`, `-nuxt` and `-email`, pinned at exactly `1.0.1` (A17). Raised only by a DS upgrade task. |
| Normative files | `SPEC.md` and `spec/schema.sql` (the canonical schema, §4.4) |
| Converted from | `cup-noobles-implementation-plan.md` (September 2026). Appendix E maps every old section to its new place. |

---

## 0. How Claude Code uses this file

This file is the contract. Code is built from it; it is not derived from code.

### 0.1 Execution protocol (every session)

1. Read §0, §2, the task's block in §6, and every section listed in the task's **Context** field.
2. Execute exactly **one task** per session. Do not start the next task, even if it looks small.
3. Implement only the Verify IDs and REQs listed on the task. If the task seems to need work they don't cover, stop and ask.
4. **Never invent business values**: prices, rates, payment windows, hold periods, purchase limits, policy or legal text, fiscal data, supplier data. **Never invent brand values**: they come only from the Design System (CR-45, CR-46). Valid sources are §2, an ADR, or the owner in chat. Anything else is registered in §2.4. Part A may use a stand-in only where §2.5 lists one.
5. If this spec contradicts itself, an ADR, or a Design System doc, stop. Quote both passages to the owner and wait for a decision. Do not pick one silently.
6. A 🔒 item in §2.4 that blocks the task means stop and ask, unless §2.5 gives a Part A stand-in.
7. Third-party services are reached only through the adapter layer (§4.3). Part A makes no outbound connection beyond package installs (A13).
8. Before starting, check the gate: every task under **Depends on** is `[x]`; the CI run of the last push is green; the working tree is clean.
9. Work only on tasks tagged with the release in progress (§1.2), unless the owner says otherwise.
10. Before reporting done, complete the Definition of Done in §0.2 and report each item as pass or fail, with evidence.
11. When the task is done, commit it as `T<id>: <task title>`. Then change its checkbox in §6 from `[ ]` to `[x]`, add the date and that commit's short SHA, and commit that change as `T<id>: mark done`.
12. Never push, deploy, publish, or change GitHub settings or a third-party dashboard unless the task says so and the owner confirms in chat.
13. When the owner must decide something, present the options, a recommendation, and a request for a one-letter reply. For anything visual, also publish a comparison page, as in the Design System's owner-decision rule.

### 0.2 Definition of Done

There are two reports. Every task produces a **task report**. The last in-scope task of each phase is marked `Gate: phase-close` and also produces a **phase-close report**. The next phase starts only after its phase-close report is complete (OA-03).

#### Task report (every task)

```text
## Task report — T<id> <title>

- [ ] Scope: files changed are limited to this task. <list>
- [ ] Verify IDs: every ID on the task has a named test, and it passes. <ID → test name>
- [ ] New tests: <test names>, in layers <unit / property / integration / concurrency / API / contract / migration / architecture / component / E2E / a11y>
- [ ] `make test` green: <final summary lines>. 0 failed; skips only with a reason naming a plan ID.
- [ ] Task specs: `make e2e FILES=<the task's Playwright specs>` green on both projects <summary> (tasks with E2E specs; otherwise n/a)
- [ ] Previous CI run green: <link to the run, or "first push">
- [ ] Existing tests: none modified, OR each change listed with the spec change that requires it (CR-38)
- [ ] Migrations: `make check-migrations` clean; new data migrations have backward tests (tasks that touch models; otherwise n/a)
- [ ] OpenAPI: snapshot unchanged, OR updated with `make schema-update`, with types regenerated
- [ ] Coverage (reported, gated at phase close): critical <x>% · backend <y>% · composables <z>%
- [ ] Sources: no business or brand value was added without a source (§2, an ADR, or the owner). New unknowns are registered in §2.4.
- [ ] Judgment calls: technical choices made without `/decide` (OA-18), each with the reason and how to undo it, or none
- [ ] Reviews: `/review` and `/ui-review` ran where §0.5 requires; each finding is fixed or registered
- [ ] Docs: README, RUNBOOK and §4.7 updated if commands, env vars or operations changed
- [ ] 🔒 Blocking items: none met, OR stopped and asked (<ID>)
- [ ] [manual] items: <list, with result>
- [ ] Commits: `T<id>: <title>`, then `T<id>: mark done`
```

#### Phase-close report (the task marked `Gate: phase-close`)

```text
## Phase-close report — Phase <n>

- [ ] Every task of the phase in the current release is [x]
- [ ] `make test-all` green: the local summary, or the green CI run for the closing commit <link>
- [ ] Verify IDs: every in-scope ID of the phase resolves to a passing test (traceability output)
- [ ] Coverage gates: critical ≥ 95 · backend ≥ 85 · composables ≥ 80. Ratchet: no scope decreased; baseline updated if any rose
- [ ] Register: every 🔒 item and design gap owned by this phase is Resolved, or Deferred with a reason
- [ ] [manual] items of the phase: <list, with result>
```

A task with any box it cannot tick is not done. Say which box and why, and do not start the next task.

### 0.3 Commands

The targets are defined in T1.12–T1.14. Every target runs inside the compose environment, so local runs and CI use the same images. On success a target prints a short summary; on failure it prints the full output of the failing step only.

| Command | Runs | Used by |
|---|---|---|
| `make test` | ruff, mypy, eslint, vue-tsc; the register check; pytest without the `slow` and `sandbox` markers (hypothesis `dev` profile); Vitest. Coverage is reported, not gated. | Every task |
| `make e2e FILES=<specs>` | The named Playwright specs on both projects, with axe, against the compose E2E stack | Tasks that add or change E2E specs |
| `make check-migrations` | `makemigrations --check --dry-run` | Tasks that touch models |
| `make test-all` | Everything in `make test`, plus the `slow` tests, hypothesis `ci`, full schemathesis, the migration round trip, `makemigrations --check`, all Playwright specs with axe, Lighthouse budgets, coverage gates, the coverage ratchet, and the traceability check for the current release | Phase close; CI on every push and pull request |
| `make test-integrations` | Installs the `integrations` dependency group, then runs the tests marked `integrations` (vendor adapters against fake clients) with sockets still disabled | From Phase 16; CI job `test-integrations` |
| `make test-sandbox` | Installs the `integrations` dependency group, then runs the `sandbox` contract tests with sockets enabled | Phase 16 only |
| `make schema-update` | Regenerates `openapi.snapshot.yml` and `web/app/types/api.d.ts` | Intentional API changes |
| `make coverage-ratchet` | Rewrites `coverage-baseline.json` after coverage rises | The same commit as the change |
| `make test-all-offline` | Builds every image (the only network step), then `make test-all` with the project network `internal: true` | Local acceptance (15.5) |
| `make clean-clone-check` | Clones into a temporary directory and runs `make test-all-offline` there | Reproduces the CI clean-clone job locally |
| `make demo` / `make demo-reset` | Starts the stack, runs `seed_demo --reset`, and prints the URLs and demo credentials | Demos (15.7) |

CI (`.github/workflows/ci.yml`) runs `make test-all` on every push and pull request, and cancels a run superseded by a newer push to the same branch. From Phase 16, a second job runs `make test-integrations`. Branch protection on `main` requires that check.

### 0.4 IDs and cross-references

| ID | Meaning | Rule |
|---|---|---|
| `T<phase>.<n>` | A task in §6 | Identity-mapped from the plan: `T4.3` is plan task `4.3`. A split task takes letter suffixes (`T2.1a`, `T2.1b`). An absorbed task is struck through with "absorbed by `T<id>`". A new task takes the next free number in its phase (for example T1.15). Never renumbered. |
| `T1`–`T19` | An order transition in the 8.A table | Unchanged from the plan. A transition ID has no dot; a task ID always has one. |
| `P<phase>-V<NN>` | A Verify item | Unchanged from the plan. The test name contains the ID in lowercase with underscores (`test_p4_v01_…`). |
| `PAY-NN`, `CAR-NN` | Contract scenarios (9.13, 10.13) | Unchanged |
| `REQ-###` | A cross-cutting requirement in §3 | Its acceptance criteria are Verify IDs |
| `CR-##` | A carried-forward rule (§2.1) | |
| `C-##` | A conflict and its resolution (§2.2) | |
| `A<n>` | An assumption (§2.3) | A1–A14 unchanged from the plan; new ones start at A15 |
| `S<n>`, `D<n>`, `G<n>` | Signup, business decision, design gap (§2.4) | Unchanged from the plan; new ones continue the sequence |
| `DSR-##` | A request to the Design System (§2.4) | Resolved by a DS release |
| `R-##` | A risk (§7) | |
| `OA-##` | An owner answer on record (§2.6) | |
| `ADR-NNNN` | A decision record in `docs/decisions/` | Every resolution cites one |
| `R1`, `R2` | Release tags (§1.2) | A task carries `Release:`. A deferred Verify ID carries `[R2]` beside its ID, the same way the plan tags `[manual]`. |
| `DS:` | Anything in the Design System repository | For example `DS:REQ-016`, `DS:ADR-0051`, `DS:formatting.md`. Its IDs never collide with this spec's. |
| `GE:` | The owner's execution guide, an internal document | Cited by ID only (`GE:T31`, `GE:§7.1`, `GE:M1`). Its figures, suppliers, budgets and dates are never copied here (CR-48). |

A section of this spec is cited as `§N`. Lettered sections and task IDs inside a phase (`8.A`, `9.A rule 4`, `7.9`) keep their plan numbers, because they live inside their phase in §6.

### 0.5 Skills and third-party tools

Sessions on this repository use only the skills below and Claude's built-in tools (OA-13).

| Skill | Source | When it runs | What it may do |
|---|---|---|---|
| `task` | Our own, adapted from the Design System's `/task` skill | `/task T4.3`, one task per session | Executes one task by §0.1 and §0.2 |
| `review` | Adapted from `ponytail-review` (`DietrichGebert/ponytail` at `09c434a`, MIT) | On demand, and required before the phase-close report of Phases 4, 8, 9 and 16 | Reports findings only. `SPEC.md` is authoritative: a finding that contradicts it becomes a question for the owner, never an edit. |
| `ui-review` | Vercel Web Interface Guidelines, a pinned copy in `docs/review/web-interface-guidelines.md` (`vercel-labs/web-interface-guidelines` at `434b7f9`, MIT) | Before the task report of every storefront task in Phases 12–14 | Reports findings. The Design System wins where they disagree: copy casing and voice follow DS microcopy and voice, focus and every visual style belong to the DS (DS:ADR-0009, CR-27). React advice is mapped to its Nuxt equivalent. |
| `decide` | Our own | When the owner answers an open item | Records the owner answer, writes the ADR, updates §2.4, removes the matching `xfail` markers, and bumps the spec version and change log |

Rules:

1. No third-party plugin, hook, MCP server or always-on rule set is added to the repository.
2. An adopted third-party skill is copied into `.claude/skills/<name>/`, pinned to its source commit, keeps its license file, is adapted to this spec, and is mirrored into `.agents/skills/<name>/`.
3. Nothing a skill produces counts as proof unless it is a named test in the suite (§4.6). Checks in the built-in browser help debugging only.
4. Playwright locators follow this order: role, label, text, then test ID. No test waits for `networkidle` (DS T5.7).

Tools considered and not adopted (OA-13):

| Tool | Why not | Allowed use |
|---|---|---|
| caveman | Its own eval shows about 3 % fewer output tokens than a plain "be concise" instruction. The CLI routes agent traffic through a proxy, sends telemetry by default, and its "Auto" routing sends prompts and attached files to a third-party cloud. | The voice by hand in chat only. Never for task reports, decision questions, docs or commits. |
| ponytail (always-on) | Its rules reject abstractions this spec requires (the adapters, a manual-only `InvoiceProvider`) and prefer one test over the coverage gates | Only through the adapted `review` skill |
| playwright-skill | A second, unpinned Playwright and browser outside the project; its throwaway scripts don't count as tests | Its two conventions, rule 4 above |
| graphify | Nothing to map in a new repository. It adds a CLI, a git hook and an `AGENTS.md` section that would break the mirror rule, and its document pass sends documents to a model. | Reconsider after local acceptance (Phase 15) if exploration cost is high |
| taste-skill | Its house rules ban the brand (a near-black ground with a neon accent and glow, glowing buttons), and it picks palettes, type and photos itself | None |
| awesome-design-md | Other brands' design languages. Brand values come only from the Design System. | None |

---

## 1. Overview

### 1.1 Goal

Build the Cup Noobles online store: a Django + DRF backend, a Nuxt 4 storefront rendered on the server and built from the Cup Noobles Design System, and PostgreSQL as the source of truth, with Mercado Pago for payments and AWS Lightsail for hosting.

The work has two parts:

- **Part A — local (Phases 1–15).** Runs entirely on one machine under `docker compose`, with every third-party service replaced by a mock. It ends in **local acceptance** (Phase 15).
- **Part B — production (Phases 16–22).** Adds the real integrations, deployment, observability and launch.

### 1.2 Scope and releases

The spec carries no calendar dates (OA-06). Releases are named by what they contain:

- **Release 1 (R1)** is what the owner's execution guide needs for the store to go live: the minimum list in GE:M1 and the store items of the soft-opening checklist (GE:§7.1).
- **Release 2 (R2)** is what the guide's second purchasing phase needs, plus anything deferred below.

Tasks and Verify IDs tagged R2 keep their IDs and stay in §6. The traceability check requires tests only for the release in progress.

| Area | Release 1 | Release 2 or later | Basis |
|---|---|---|---|
| Catalog, product pages, search, facets | Phases 2, 3, 5 and 12 | — | GE:M1 |
| Inventory | Phase 4, without counter sales. Adds the "Recibir mercancía" admin action (G20) and an optional bin location (G34). | Counter sales, if the warehouse ever opens to the public or for events | GE:§1.4; OA-11 |
| Checkout and shipping | Guest checkout; delivery only; shipping by zone table with a free-shipping threshold | Pickup (T8, T13–T15, 10.2, 10.8) | OA-08; GE:M1 |
| Payments and refunds | Cards, OXXO, SPEI and meses sin intereses through Mercado Pago; refunds, including the manual OXXO refund (9.8) | — | GE:M1 |
| Per-customer purchase limits | A limit per variant, enforced at checkout (G31, D15) | — | GE:§7.1, GE:T20, GE:R10 |
| Pre-launch catalog mode | The store is live while the catalog stays hidden; staff make real test purchases; everything is published at once (G32) | — | GE:T31, GE:T35, GE:T38 |
| CFDI | Manual: optional fiscal data at checkout, an admin queue, upload of the PDF and XML, an email to the customer, a global-invoice export, and a flag on refunds of invoiced orders. The `InvoiceProvider` interface has only a manual implementation. | Integration with a PAC, if the owner decides | OA-07; GE:M1, GE:T32 |
| Reporting | CSV exports of orders, order lines and shipments, with a unit-cost snapshot (G33) | — | GE:T34, GE:T43, GE:§5.2 |
| Customer accounts | Guest order lookup (6.7, G35) and its page `/rastrear` (14.6); postal-code autofill (6.6) | Register, login, verification, password reset, addresses, history and claiming (6.1–6.5, 6.8, the rest of Phase 14) | OA-11 |
| Pre-orders | The schema columns stay; services, UI and tests are deferred | R2, adding a closing date per pre-order (G36) | GE:§7.1, GE:§1.2 |
| Transactional email | Order confirmation, OXXO voucher, order expired, order shipped, order cancelled, refund issued, CFDI issued | Email verification, password reset, ready for pickup, pickup reminder, pre-order arrived | Follows the rows above |
| Promotions | None (A9) | Discounts or bundles, if the owner decides (GE:T46) | — |
| Design System additions | DSR-01 to DSR-07, released by the DS before Phases 11 and 12 | DSR-08 | OA-09 |

### 1.3 Non-goals

- Calendar dates and delivery deadlines. The owner's guide owns them (OA-06).
- Presenting the warehouse as a store anywhere on the site (CR-47).
- Any change to the Design System repository from a session on this repository. Missing parts are requested as DSR items and built in the DS (OA-09).
- Visual styling in the storefront, its own components where the DS has one, a light theme, or a color-mode toggle (CR-26, CR-27, CR-34).
- Changing the look of the Django admin (DS:OA-4). It stays on Django's defaults.
- A custom payment gateway, storing card data, or PCI-DSS scope beyond SAQ-A (plan 3.4).
- Kubernetes, microservices, multi-region hosting, Celery or Redis (plan 3.2, 3.5).
- Multi-country or multi-currency; mobile apps.
- A POS integration (plan Appendix D).
- Carrier rate APIs and automated label printing (A7).
- CFDI through a PAC in R1 (A8).
- Discount codes, gift cards, loyalty, bundles in R1 (A9).
- Product reviews, wishlists, abandoned-cart recovery, a recommendation engine.
- B2B or wholesale pricing, subscriptions.
- A returns (RMA) workflow beyond a manual refund and stock adjustment (A12).
- Multi-warehouse routing, real-time stock websockets, a headless CMS, A/B testing.

---

## 2. Rules, conflicts, assumptions and open items

Source key: **plan** is `cup-noobles-implementation-plan.md`. **DS** is the Design System repository at version 1.0.1. **GE** is the owner's internal execution guide (v4), cited by ID only. **OA** is an owner answer in §2.6.

### 2.1 Carried-forward rules

Each rule is binding. "Enforced by" names the check that fails when the rule is broken. A rule marked "review" has no automated check.

#### Money and pricing

| ID | Rule | Source | Enforced by |
|---|---|---|---|
| CR-01 | Money is always integer centavos of MXN. Never floats; never `Decimal` in the database. | plan §0 | `CHECK` constraints (Phase 2), money property tests (9.2) |
| CR-02 | Totals are computed in exactly one function, `orders/pricing.py::compute_totals`. The cart, checkout and order creation all call it, and the client never computes a price. | plan 7.9, 3.3 rule 6 | Totals property tests (P7-V17); review |
| CR-03 | The cart stores no prices. Prices are frozen once, when the order is created. | plan 7.3 | P7-V03, P8-V09 |

#### Inventory

| ID | Rule | Source | Enforced by |
|---|---|---|---|
| CR-04 | `available = on_hand − reserved − safety_stock`, never negative | plan Phase 4 rule 1 | `stock_reserved_le_on_hand`, P4-V06 |
| CR-05 | Every change to `on_hand` writes a `stock_ledger` row, with `balance_after`, in the same transaction | plan Phase 4 rule 2 | `test_stock_mutation_boundary`, P4-V06, P4-V07 |
| CR-06 | Reservations move `reserved`, never `on_hand` | plan Phase 4 rule 3 | P4-V03 |
| CR-07 | Every stock change takes `SELECT … FOR UPDATE` on the `stock_item` row first | plan Phase 4 rule 4 | Concurrency tests (P4-V01, P4-V14) |
| CR-08 | Pre-order quantity comes from the variant's pre-order counter and never touches shelf stock (R2) | plan Phase 4 rule 5, 10.A | P10-V07 [R2] |

#### Orders

| ID | Rule | Source | Enforced by |
|---|---|---|---|
| CR-09 | Every order state change goes through `apply_event`, which locks the order row with `SELECT … FOR UPDATE`. Nothing else assigns `order.state`. | plan 8.A, 8.1 | `test_no_direct_state_assignment` |
| CR-10 | A transition not in the 8.A table is illegal and raises `IllegalTransition` | plan 8.A | P8-V07 |

#### Payments

| ID | Rule | Source | Enforced by |
|---|---|---|---|
| CR-11 | The webhook is authoritative; the browser redirect is not | plan 9.A rule 1 | PAY-01, PAY-14 |
| CR-12 | A webhook payload's amount and status are never trusted: the payment is fetched from the provider | plan 9.A rule 2 | The mock sends ids only (9.11) |
| CR-13 | The signature is verified before anything else, and stale timestamps are rejected | plan 9.A rule 3 | PAY-11, PAY-12 |
| CR-14 | Idempotency comes from the database, keyed on the provider's notification (delivery) id, not the payment id | plan 9.A rule 4 | P2-V16, PAY-09, PAY-10 |
| CR-15 | Webhooks are acknowledged fast; a row that fails processing is retried by `process_webhooks` | plan 9.A rule 5 | P9-V17 |
| CR-16 | Processing follows the fetched state, not the event: seeing the same status twice is a no-op | plan 9.A rule 6 | PAY-10, PAY-14 |
| CR-17 | An approved payment moves the order only if its amount equals the order total | plan 9.4 rule 1 | PAY-13, P9-V07 |

#### Integration boundaries

| ID | Rule | Source | Enforced by |
|---|---|---|---|
| CR-18 | Domain code depends on an interface, never on an implementation | plan §5.A rule 1 | `test_provider_selection` |
| CR-19 | Only the adapter module imports a vendor SDK or an HTTP client used to reach a vendor | plan §5.A rule 2 | `test_vendor_imports` |
| CR-20 | Mocks are the default in dev and test settings. `prod.py` refuses any mock, and forces dev tools off. | plan §5.A rule 3 | P1-V14, P1-V16 |
| CR-21 | An unknown provider value is a startup error, not a silent fallback | plan §5.A rule 4 | P1-V15 |
| CR-22 | A mock behaves exactly like its real provider at the interface: same types, exceptions, idempotency and status vocabulary | plan §5.A rule 5, A14 | Contract suites (9.13, 10.13) |
| CR-23 | Vendor SDKs live only in the optional `integrations` dependency group | plan §5.A rule 6 | Part A image build |

#### Storefront

| ID | Rule | Source | Enforced by |
|---|---|---|---|
| CR-24 | No Pinia. Cart and session state are server state fetched over the API; ephemeral UI state uses `ref`. | plan 3.3 rule 1 | Review |
| CR-25 | The API client is generated from the OpenAPI snapshot, never written by hand | plan 3.3 rule 2, 5.5 | P5-V04, P12-V04 |
| CR-26 | UI comes from the Design System layer `@vinsmokemau/cup-noobles-nuxt`. Never hand-roll a component or primitive that the DS or Nuxt UI provides. A missing part is requested as a DSR item (§2.4). | plan 3.3 rule 3, amended by C-01; DS:ER-01, DS:C-02; OA-09 | Review |
| CR-27 | Tailwind is used for layout only. The storefront adds no colors, borders, radii, glow, shadows or fonts of its own. | plan 3.3 rule 4, amended by C-02; DS:C-03, DS:OD-11 | P12-V26; the DS raw-value lint rule once published (DSR-09) |
| CR-28 | Forms use Nuxt UI `UForm` with one Zod schema per form; the server re-validates every field | plan 3.3 rule 5 | API validation tests |
| CR-29 | Every request goes through `useApi`; there is no bare `$fetch` anywhere else | plan 12.2, 12.11 | P12-V24 |
| CR-30 | Money is formatted only by `formatMXN` and `PriceDisplay`, with `Intl.NumberFormat('es-MX')`, the currency code passed in and no suffix | plan 12.6; DS:formatting.md; resolves G19 | P12-V09 |
| CR-31 | Every displayed date and time is formatted with `Intl` and an explicit `timeZone` (G5) | DS:formatting.md | Review |
| CR-32 | Customer-facing copy is es-MX and follows DS voice and microcopy. Components receive text through props or slots. | DS:ER-04, DS:A-11, DS:voice-and-tone.md, DS:microcopy.md | Review |
| CR-33 | Layouts work at 360 px wide, with no horizontal scroll | plan 12.9; DS:ER-05 | P12-V21 |
| CR-34 | The theme is dark only, with no color-mode toggle | DS:A-02, DS:REQ-031 | Review |
| CR-35 | The accessibility target is WCAG 2.2 AA. axe runs with the WCAG 2.2 A and AA tags, and no `serious` or `critical` violation is allowed. | DS:A-10; plan §6.A | `expectNoA11yViolations` in every page-level spec (P1-V20) |
| CR-36 | Storefront tap targets are at least 44 px. That is stricter than the DS minimum of 24 px, and is reached through DS size props, never by restyling. | plan 12.9; DS:REQ-028 | P12-V21 |

#### Testing

| ID | Rule | Source | Enforced by |
|---|---|---|---|
| CR-37 | No task is done until its new tests pass and `make test` passes. No phase is done until `make test-all` passes (§0.2). | plan §6, amended by OA-03 | DoD reports, CI |
| CR-38 | Earlier tests are not edited to make new work pass. The only allowed change to an existing assertion is one this spec now requires, listed with its reason in the task report. | plan §6 consequence 2 | DoD report |
| CR-39 | No silent skips: every `skip`, `xfail`, `test.skip` or `test.fixme` carries a reason naming a plan ID | plan §6 consequence 3 | Traceability check |
| CR-40 | Tests run on PostgreSQL only; SQLite aborts the run | plan §6.A | P1-V04 |
| CR-41 | Part A makes no outbound connection | plan A13 | pytest-socket, the Playwright offline guard (P1-V08, P1-V13), P15-V13, P15-V14 |
| CR-42 | Tests build state through factories and services, never raw `objects.create` on `order` or `stock_item` | plan §6.A | Review |
| CR-43 | No `sleep()` in any test; time-dependent logic uses `time-machine` | plan §6.A | Review |
| CR-44 | Coverage never decreases | plan §6.B | `coverage_ratchet.py` (P1-V06) |

#### Business, brand and security

| ID | Rule | Source | Enforced by |
|---|---|---|---|
| CR-45 | Never invent a business value: prices, rates, windows, hold periods, limits, policy or legal text, fiscal data | plan §4 | `check_placeholders` (§2.5); review |
| CR-46 | Never invent a brand value. Colors, type, spacing, shape, effects, icons, logos, motifs and imagery come from the DS. | DS CLAUDE.md, DS:§2.1 | CR-27 test; review |
| CR-47 | The warehouse is never presented as a store: no "tienda" wording for the location, no opening hours, no pickup | GE:§1.4, GE:R12; OA-08 | Review; seed names (§2.5) |
| CR-48 | The repository is public. Internal business data never enters it: the execution guide, budgets, suppliers, margins, costs, sales targets. | OA-10 | Review |
| CR-49 | Catalog files that hold costs are never committed. The importer reads them from a path given at run time. | plan 3.6, D12; CR-48 | `.gitignore`; review |
| CR-50 | Secrets come only from the environment: never in an image, never in Git | plan 1.3, 20.5 | Review; GitHub secret scanning |

### 2.2 Conflicts and their resolutions

| ID | Conflict | Resolution | Status |
|---|---|---|---|
| C-01 | Plan 3.3 rule 3 says to use Nuxt UI and not build a design system. The Cup Noobles Design System now exists and owns the UI. | The storefront consumes the DS layer (CR-26). Commerce components are built in the storefront from DS parts (DS:OD-01). | Resolved (DS:OA-4, DS:OD-01) |
| C-02 | Plan 3.3 rule 4 gives the storefront a `main.css` with brand tokens. The DS forbids visual styling in a consuming app (DS:C-03). | The storefront does no visual styling (CR-27). Brand tokens arrive with the layer. | Resolved (DS:OD-11) |
| C-03 | The storefront needs parts the DS lacks: room for price and availability in `CnMediaCard`, an attribute list, an image gallery, rows inside an email card, and a raster email logo. | Each is requested as a DSR item and released by the DS before the phase that needs it (§2.4). | Resolved (OA-09) |
| C-04 | Plan A1, pickup (T8, T13–T15, 10.2) and counter sales (A11, 4.5) assume a store open to the public. GE:§1.4 says the warehouse is never presented as a store. | R1 is delivery only, with no counter sales. A1 and A11 are rewritten (§2.3); pickup and counter sales move to a later release. | Resolved (OA-08, OA-11) |
| C-05 | Plan A8 has no CFDI in v1. GE:M1 requires CFDI to the customer, possibly manual at first, and GE:T32 a global invoice. | Manual CFDI in R1 (A8 rewritten; §1.2) | Resolved (OA-07) |
| C-06 | Plan Phase 15 is called "MVP acceptance" and is local. In GE:M1, "MVP" means the live store. | Phase 15 becomes "local acceptance". This spec says "Release 1" for the live store and never uses "MVP" for Part A. | Resolved (OA-11) |
| C-07 | Plan §6 runs the whole suite on every task. The owner wants a light suite per task and the full suite per phase and in CI. | §0.2 and CR-37 | Resolved (OA-03) |
| C-08 | Plan 12.4 formats prices as `$1,234.00 MXN`; plan 12.6 gives the `Intl` output with no suffix (G19). | DS:formatting.md decides: the `Intl` output, with no symbol by hand and no suffix (CR-30) | Resolved (DS:formatting.md); ADR in T1.15 |
| C-09 | The DS email layout has six fixed parts and is built only from DS components. The plan has 11 templates and commerce rows such as order lines. | The seven R1 templates fit the six-part layout. Rows inside the card are a DS request (DSR-04). | Partly resolved (OA-09); DSR-04 open |
| C-10 | The DS photo standard says "no text inside the image" (DS:ADR-0057). Product packaging photos always carry printed text. | The DS clarifies the rule's scope for product photos (DSR-07) | Open |
| C-11 | Plan 1.5 installs `@nuxt/ui` on its own and uses npm. The DS layer brings Nuxt UI 4.11.2 and Tailwind 4.3.3, and its install path is verified with pnpm. | `web/` uses pnpm, gets Nuxt UI only through the layer, and pins Nuxt to the version of the DS consumer fixture (4.5.2) | Resolved (OA-12) |
| C-12 | Plan S5 wants a private repository with branch protection. On GitHub Free, branch protection is available only to public repositories (DS:OD-14). | The repository is public (OA-10), and CR-48 keeps internal data out | Resolved (OA-10) |
| C-13 | DS rules ER-01 to ER-06 cite plan sections (§3.3, §6, Phases 11–12) that this spec renumbers | Appendix E keeps every old section findable. A DS amendment that updates those citations is optional. | Open (low) |
| C-14 | Plan §0 uses commits like `feat(inventory): 4.3 …`. The DS `/task` skill commits `T0.1: <title>`. | This spec uses `T<id>: <title>` (§0.1 step 11), so the task skill is shared | Resolved (this spec) |

### 2.3 Assumptions

Each assumption is cheap to reverse unless its row says otherwise. A1–A14 keep their plan IDs. The rewritten ones say so.

| # | Assumption | Why it matters | Cost to change later | Release |
|---|---|---|---|---|
| A1 | **Rewritten.** One stock location: a warehouse (`kind = 'warehouse'`) that is not a pickup point and is not open to the public. Inventory is still modelled per location, so a second location is data. | GE:§1.4; OA-08 | Low | R1 |
| A2 | Prices are stored and displayed IVA-included (16 %). Tax is decomposed for reporting, not added at checkout. | GE:M1 asks for visible prices with IVA | Low | R1 |
| A3 | MXN only, single locale `es-MX` | No FX, no i18n framework | Medium | R1 |
| A4 | Launch scale: under ~500 orders a month, under ~5,000 SKUs, under ~50k monthly pageviews. Consistent with the owner's internal sales model, which is not reproduced here. | Justifies one small server and a small database | Low | R1 |
| A5 | Pre-orders are charged in full at order time | Avoids deposits and partial capture | High | R2 |
| A6 | An order with pre-order items ships complete (D8) | Removes partial fulfillment | Medium | R2 |
| A7 | Shipping is a flat rate by zone and order subtotal, with one carrier and no live carrier rating | GE:M1 asks for shipping "calculated or by table" with a configurable free-shipping threshold | Low | R1 |
| A8 | **Rewritten.** CFDI is issued by hand in R1. The store captures the customer's fiscal data at checkout, keeps a queue of requests, stores the folio, UUID, PDF and XML the owner uploads, emails them, exports the orders a global invoice needs, and flags refunds of invoiced orders. An `InvoiceProvider` interface has only a manual implementation, so a PAC can replace it later. | GE:M1, GE:T32; OA-07 | Medium | R1 |
| A9 | No discount codes, gift cards, loyalty or bundles. `discount_cents` exists and is always 0. | One line of pricing arithmetic | Low | R1 (R2 if the owner decides, GE:T46) |
| A10 | The developer can use Git, a shell and Docker, and is weakest on frontend | Drives the generated client and the server-state rules | n/a | R1 |
| A11 | **Rewritten.** No in-person sales in R1, so no counter-sale page. If the warehouse opens to the public or sells at events, counter sales return in a later release. | OA-11 | Low | R2 |
| A12 | No returns workflow beyond a manual refund plus a stock adjustment in the admin. A refund of an invoiced order is flagged for the accountant. | Returns are rare at this volume | Low | R1 |
| A13 | Part A runs offline: every Part A phase, test and demo runs on one machine, with no outbound connection beyond package installs | Business logic is proven before any account or credential exists | Low | R1 |
| A14 | Each mock behaves exactly like its real provider at the interface level; the shared contract suites run against both | A mock easier than the real thing hides bugs until Part B | Medium | R1 |
| A15 | One maintainer: the owner is the developer and the business owner. Governance is sized for one person, and decisions are recorded as owner answers and ADRs. | OA-04; DS:A-01 | n/a | R1 |
| A16 | Guest checkout only in R1. A customer is identified by email, and also by phone and shipping address for purchase limits (G31). | OA-11 | Medium | R1 |
| A17 | The three DS packages are pinned at an exact version, currently `1.0.1`. A DS upgrade is its own task. | OA-12; DS:R-01 | Low | R1 |
| A18 | The repository is public on GitHub Free, created by the owner | OA-10 | Low | R1 |
| A19 | The weekly dashboard and the monthly report are built by the owner from admin CSV exports. The store has no reporting screens. | GE:T34, GE:T43 | Low | R1 |

### 2.4 Open-items register

Status values: **Open**; **Decided** (an owner answer exists; its ADR is written in T1.15, a new task that seeds the ADRs); **Resolved (ADR-NNNN)**; **Deferred (R2)**. An open design gap has its dependent tests written against the proposed resolution and marked `xfail(strict=True, reason="G<n>")` (plan Appendix F). `scripts/check_register.py` fails if a test, an `xfail` reason or a code comment cites an ID that doesn't exist here, or if a resolved item still has an `xfail`.

#### Signups and accounts (S)

| ID | Item | Needed by | Release | Status |
|---|---|---|---|---|
| S1 | AWS account with root MFA, an IAM user for deploys, and a billing alarm at $80 | Phase 18 | R1 | Open |
| S2 | Mercado Pago business account. Test credentials first; production identity verification takes days, so start it during Part A. | Phase 16 | R1 | Open |
| S3 | Domain registration. GE:T04 also needs a mailbox on the domain early, outside any phase. | Phase 17 | R1 | Open |
| S4 | Transactional email provider (Resend or AWS SES), with SPF, DKIM and DMARC. SES starts in sandbox; request production access early. | Phase 17 | R1 | Open |
| S5 | **Rewritten.** Public GitHub repository, created by the owner. Name pending. | Phase 1 | R1 | Decided (OA-10); name open |
| S6 | Sentry (free tier) | Phase 21 | R1 | Open |
| S7 | Carrier or aggregator account for buying labels by hand | Phase 19 | R1 | Open |
| S8 | **New.** Read access to the three private DS packages on GitHub Packages: in each package's settings, grant this repository Actions read access; for local installs, a classic personal access token with `read:packages` in the user-level `.npmrc` (DS:using-the-system.md) | T1.5 | R1 | Resolved (ADR-0026) |

#### Business decisions (D)

| ID | Question | Needed by | Release | Part A stand-in | Status |
|---|---|---|---|---|---|
| D1 | Legal entity and RFC for the legal pages and the Mercado Pago account. GE assumes a persona física con actividad empresarial, with the exact régimen set by the accountant. | Phase 20 | R1 | — | Open |
| D2 | Terms of service, aviso de privacidad, shipping and returns policy, and the purchase-limits text. The owner drafts them (GE:T23), and a lawyer or a vetted template checks them. The pre-order text is R2. | Phase 22 | R1 | Placeholder pages | Open |
| D3 | Will you issue CFDI? | Phase 2 | R1 | — | Decided (OA-07): manual in R1 (A8) |
| D4 | **Rewritten.** The warehouse location's internal code, name and address. It is never shown as a store (CR-47). The pickup hold period moves to R2 with pickup. | Phase 22 | R1 | §2.5 | Open |
| D5 | Shipping zones, rates and the free-shipping threshold (GE:T20) | Phase 22 | R1 | §2.5 | Open |
| D6 | Payment window for OXXO and SPEI. Stock is held the whole time. | Phase 16 | R1 | §2.5 | Open |
| D7 | Meses sin intereses: enable it, and at which terms? The store absorbs the fee. | Phase 16 | R1 | §2.5 | Open |
| D8 | Mixed pre-order and in-stock orders ship complete (A6), or in-stock items ship first | — | R2 | — | Deferred (R2) |
| D9 | Pre-order cancellation policy | — | R2 | — | Deferred (R2) |
| D10 | Show exact stock counts, a low-stock badge, or only in or out of stock (G13) | Phase 22 | R1 | Low-stock badge, no counts (5.3) | Decided (ADR-0037) |
| D11 | Brand assets: logo, colors, photography standards | — | R1 | — | Resolved by the DS: logos DS:ADR-0016, icons DS:ADR-0012, focus DS:ADR-0009, photos DS:ADR-0056 and DS:ADR-0057, colors DS:BR-01 to BR-03. ADR in T1.15. |
| D12 | The initial catalog file for the importer (3.6), from GE:T31. It is never committed (CR-49). | Phase 22 | R1 | `seed_demo`, generated CSVs | Open |
| D13 | Mercado Pago settlement speed. Faster settlement costs a higher fee. | Phase 16 | R1 | — | Open |
| D14 | **New.** Launch product types and their attribute schemas. GE adds an accessories type (GE:§0.3), puts apparel after launch, and asks for language, edition and condition (sealed) on TCG and board games (GE:M1, GE:§7.1). | T2.8 | R1 | §2.5 | Open |
| D15 | **New.** The purchase-limit value of each limited variant, and the length of the window the guard counts over, in days (`PURCHASE_LIMIT_WINDOW_DAYS`) (GE:T20). The mechanism is G31 (ADR-0030). | Phase 22 | R1 | Factory values in tests | Open |
| D16 | **New.** CFDI details for the accountant: the list of fiscal fields to capture, how long a customer has to request a CFDI, the global-invoice period, and how a refund of an invoiced order is handled | Fields: T2.1. The rest: Phase 22. | R1 | §2.5 | Open |
| D17 | **New.** Out-of-stock interest list: link to the external form or WhatsApp list of GE:T26, or show nothing | Phase 12 | R1 | Nothing shown | Open |
| D18 | **New.** Analytics: which tool, if any (for example Plausible or GA4)? The aviso de privacidad must match (D2). | Phase 22 | R1 | None installed | Open |

#### Design gaps (G)

G1–G22 come from plan Appendix F. G23–G30 were found while converting the plan. G31–G36 come from the execution guide. A proposal is not applied until the owner decides.

| ID | Owning phase | Exposed by | Gap | Proposed resolution (not applied) | Release | Status |
|---|---|---|---|---|---|---|
| G1 | 1 | P1-V11, P1-V17 | `/api/health/` is verified in Phase 1 but specified only in 20.4 | Move the endpoint into Phase 1; 20.4 keeps the Lightsail health-check configuration | R1 | Resolved (ADR-0028) |
| G2 | 4 | P4-V17, P8-V01 | The outbox writer is defined in 11.1, but Phases 4 and 8 already write outbox rows. Widened from the plan's Phase 6, which is now R2. | Move `enqueue_email()` (the write only, not sending) into Phase 4 | R1 | Resolved (ADR-0036) |
| G3 | 8 | P8-V03, P8-V08 | 8.4 stores the `Idempotency-Key` "on the order", but no column holds it; reuse with a different body, the key's scope and its lifetime are undefined | `idempotency_key` plus a request fingerprint, with a partial unique index per cart token; a mismatched body returns 422 `idempotency_key_reused`. Schema change. | R1 | Resolved (ADR-0030) |
| G4 | 8 | P8-V09, P13-V19 | A price change between the last view and "Pagar" applies silently | Checkout takes `expected_total_cents`; a mismatch returns 409 with fresh totals and reserves nothing | R1 | Resolved (ADR-0042) |
| G5 | 8 | P8-V12 | The timezone of the order-number year is unspecified, and so is the per-year sequence. Widened: DS:formatting.md requires an explicit `timeZone` for every displayed date (CR-31). | `America/Mexico_City` as the store timezone for numbering and display; one Postgres sequence per year, created on first use | R1 | Resolved (ADR-0030) |
| G6 | 8 | P8-V17 | Cancelling an order whose pre-order reservations are committed is undefined | `cancel_preorder_allocation(order)`, called from T16 and T19 | R2 | Deferred (R2) |
| G7 | 9 | P9-V13, P9-V17 | Webhook processing failures have no retry cap | 10 attempts with exponential backoff, then mark failed and alert | R1 | Resolved (ADR-0044) |
| G8 | 9 | P9-V10 | Future timestamps and clock skew are unspecified | Accept `abs(now − ts) ≤ WEBHOOK_MAX_AGE_SECONDS` | R1 | Resolved (ADR-0044) |
| G9 | 10 | P10-V17 | FIFO pre-order allocation has no tie-break for equal `paid_at` | Break ties by `order.id` ascending | R2 | Deferred (R2) |
| G10 | 10 | P10-V13 | The pickup reminder has no defined window | Send at ≤ 24 h remaining, with a dedupe key | R2 | Deferred (R2) |
| G11 | 9 | P9-V21 | T1 reserves stock for the card TTL before the payment method is known; an OXXO voucher can arrive for an expired order | A `pending` notification for an expired or cancelled order alerts and cancels the voucher; the order stays as it is (built in T9.15). The separate checkout-session TTL was not adopted. | R1 | Resolved (ADR-0046) |
| G12 | 3 | P3-V09 | `import_catalog` doesn't say what happens to valid rows when some rows are invalid | All or nothing per file, reporting every invalid row | R1 | Resolved (ADR-0033) |
| G13 | 5 | P5-V07 | D10 suggests a badge "under 5"; 5.3 defines `low_stock` as 1 ≤ available ≤ 5 | Decide together with D10 | R1 | Resolved (ADR-0037) |
| G14 | 9 | P9-V14 | A webhook and `reconcile_payments` processing one approval concurrently: the second `apply_event` raises `IllegalTransition` under the lock | Treat it as `webhook_no_op` when the order already reflects the status | R1 | Resolved (ADR-0047) |
| G15 | 4 | P4-V16 | `commit_reservations` is not specified as idempotent | A second commit of committed reservations is a no-op | R1 | Resolved (ADR-0036) |
| G16 | 10 | P10-V21 | T9 into `ready_for_pickup` doesn't set `pickup_deadline_at` | T9 sets it | R2 | Deferred (R2) |
| G17 | 11 | P11-V10 | `send_outbox` doesn't claim rows; an overlapping run can send an email twice | Claim rows with `SELECT … FOR UPDATE SKIP LOCKED` | R1 | Open |
| G18 | 12 | P12-V01, P12-V22, P12-V25 | `nitro.devProxy` exists only in development, so a production build has no route from server rendering to Django | Nitro `routeRules` proxy `/api/**` to a server-only API target | R1 | Open |
| G19 | 12 | P12-V09 | `$1,234.00 MXN` (12.4) against the `Intl` output (12.6) | Decided by DS:formatting.md (C-08, CR-30) | R1 | Decided; ADR in T1.15 |
| G20 | 10 | P15-V05, demo step 9 | Receiving goods has no admin page, but it is daily work (GE:T30, GE:T35, GE:§5.2) | A "Recibir mercancía" admin action (variant, location, quantity) calling `receive_stock` in R1, and `receive_preorder_stock` for pre-order variants in R2 | R1 | Resolved (ADR-0035) |
| G21 | 13 | P13-V13, P13-V14 | Guest landing pages must poll the order, but the guest endpoint needs number and email and allows 5 calls an hour | A short-lived signed order-status token, carried in `back_urls`, for a read-only status endpoint | R1 | Open |
| G22 | 13 | P13-V15 | No endpoint retries payment for a `pending_payment` order, and when the cart counts as converted was undefined (decided: at T1, ADR-0049, built in T9.16) | `POST /api/orders/{public_id}/pay/` returns a fresh `checkout_url`; the cart is converted at T1 (adopted, ADR-0049) | R1 | Open (the endpoint) |
| G23 | 20 | plan Appendix B | The production topology (20.A) has no process that runs the scheduled jobs | A fourth container from the `api` image running supercronic, or a process supervisor inside `api` | R1 | Open |
| G24 | 4 | P4-V07 | `check_stock_integrity` is tested in Phase 4 but specified in 21.7 | Move the command into Phase 4; 21.7 keeps only its daily schedule | R1 | Resolved (ADR-0034) |
| G25 | 8 | P8-V06, 8.4 | Phase 8 needs a payment provider (`create_checkout`, `refund`) before the mock exists (9.9); 1.11 creates only the interfaces | Build those two mock methods in Phase 8, and the rest of the mock in Phase 9 | R1 | Resolved (ADR-0041) |
| G26 | 8 | T18, P8-V07 | A `partially_refunded` order "stays fulfillable", but no transition leaves that state | Either add the fulfillment transitions from it, or record partial refunds on the payment without changing the order state | R1 | Resolved (ADR-0043) |
| G27 | 8 | T17, A12, 9.4 rule 3, GE:T36 | A refund after delivery (a return), or of a late payment on an expired or cancelled order, can't be applied: those states are terminal | Allow the refund events from `completed`, `expired` and `cancelled` as recorded payment events | R1 | Resolved (ADR-0043) |
| G28 | 12 | 12.A, P12-V13, 5.1 | "Featured" and "related" products have no data model or rule | A featured flag with a position on the product; related products by shared franchise or category | R1 | Resolved (ADR-0030) |
| G29 | 1 | P1-V03, 1.9, P15-V14 | CI and branch protection are verified only in Phase 20, though Part A relies on them | Verify them in Phase 1, now that the repository is public; branch protection as a `[manual]` item | R1 | Resolved (ADR-0029) |
| G30 | 6 | 6.6, Phase 22 | 6.6 calls the SEPOMEX data optional, but the launch checklist requires it | The full dataset is a launch requirement; the sample stays for Part A | R1 | Resolved (ADR-0039) |
| G31 | 8 | GE:§7.1, GE:T20, GE:R10 | Purchase limits per customer are needed at launch, and no mechanism exists. With guest checkout, a customer has no account. | A limit per variant set in the admin; the T1 guard counts units in pending and paid orders that match the email, phone or shipping address within a window. The values are D15. | R1 | Resolved (ADR-0030) |
| G32 | 3, 5, 12 | GE:T31, GE:T35, GE:T38, GE:M1 | The store must be live with real test purchases while the catalog is hidden, then published at once. Catalog responses are publicly cached (5.6). | A site-wide pre-launch switch. The public sees a "próximamente" page, which also serves GE:T04. Logged-in staff browse and buy, and their requests bypass the catalog cache. Going live is a bulk publish plus turning the switch off. | R1 | Resolved (ADR-0038) |
| G33 | 2, 8, 10 | GE:T34, GE:T43, GE:§5.2 | The weekly dashboard and monthly report need data. Margin needs the unit cost at the time of sale, and `order_line` has no cost snapshot. | Admin CSV exports of orders, lines and shipments; a `unit_cost_cents` snapshot on `order_line` (schema change). Shipped-within-48-h and stock-cancellation counts come from timestamps and cancel reasons. | R1 | Resolved (ADR-0030) |
| G34 | 4 | GE:§7.1, GE:T28 | Picking needs a bin location ("ubicación"), which the schema lacks | An optional text field on `stock_item`, shown on the order's packing view | R1 | Resolved (ADR-0030) |
| G35 | 6 | 6.7 | The guest lookup sends the customer's email in the query string (`GET …/lookup/?number=&email=`), where proxy, CDN and error logs record it | `POST` with a JSON body, keeping the rate limit and the identical 404 for a wrong email | R1 | Resolved (ADR-0040) |
| G36 | 10 | GE:§1.2 | Pre-orders need a closing date, which the schema lacks | `preorder_closes_at` on the variant; `reserve()` rejects pre-orders after it | R2 | Deferred (R2) |
| G37 | 4 | P4-V03, T8.6 | `expire_reservations` (4.3) moves the order `pending_payment → expired`, but in Phase 4 orders are drafts and `apply_event` arrives in Phase 8; `advance_orders` (8.6) also fires T5, so two jobs own expiry | In Phase 4 the job releases lapsed holds only. From Phase 8 it fires T5 through `apply_event`, and `advance_orders` stops firing T5. P4-V03 asserts the order state from Phase 8 on. | R1 | Resolved (ADR-0036) |
| G38 | 4 | P4-V17, 21.4 | `low_stock_report` and `daily_digest` email "the owner", but no setting names the address | An `OWNER_ALERT_EMAIL` setting (§4.7): a `.test` address in development, the owner's monitored inbox in production | R1 | Resolved (ADR-0036) |
| G39 | 3 | 3.6 | The importer's `image_urls` column implies downloading images, which A13 forbids in Part A and nothing specifies for production | The column holds file paths relative to an images folder given at run time; the importer never makes a network call, and a remote URL is a row error | R1 | Open |
| G40 | 2 | P2-V01 | Django 5.2 applies the schema's `ON DELETE` rules in Python, not in the database: an unnamed foreign key has `NO ACTION` and is deferrable, so a raw SQL delete cannot cascade or null out dependents | Accepted as is. Only the four named foreign keys (`product_image_variant_fk`, `reservation_order_fk`, `stock_ledger_order_fk`, `cart_converted_order_fk`) carry the exact rules. P2-V01 compares the others by columns and target table. Revisit on Django 6.0 (native `db_on_delete`) | R1 | Resolved (ADR-0031) |
| G41 | 2 | 22.3 | T2.7 loads `mx_state` only through `seed_dev_defaults`, a dev command whose output `check_placeholders` treats as stand-ins; the 32 states are real data that production needs too, and no task loads them there | A separate `manage.py seed_states` command (idempotent, running `apps.shipping.seeds.seed_states`), run by the deploy step; `seed_dev_defaults` keeps calling the same function | R1 | Resolved (ADR-0032) |
| G42 | 20 | 4.5, 20.2 | The Node2Shell fix (CVE-2026-111497) needs Node 22.23.4 or later. Part A pins it in `web/Dockerfile` and CI, but 20.2 runs the production image on the floating tag `node:22-slim`, which is not pinned. | The production `web/Dockerfile` pins `node:22.23.4-slim` or later, and the pin is raised on each Node security release | R1 | Open |
| G43 | 20 | T6.7b, 20.A | `django-ratelimit` counts in a cache, and the stack has no Redis or memcached (ADR-0006). The api uses the local-memory cache, whose counters are per process: exact for one api process, looser by the number of workers. The library's check `django_ratelimit.E003` is silenced for this reason. | The production topology (20.A) runs the api as a single process (threads allowed), or the owner picks a shared store | R1 | Open |
| G44 | 7 | T7.6, Phase 13 | The `cart` table has no postal-code column (`spec/schema.sql`), so T7.6 quotes shipping from the postal code the request carries: the `POST /api/cart/fulfillment/` body, or the `postal_code` query parameter of `GET /api/cart/`. T7.1 says the cart response carries a quote once `fulfillment_method` is set, which a stored code would give without the parameter. | Keep the query parameter (OA-46). Phase 13 checks whether the storefront finds it awkward; if so, a nullable `cart.postal_code` is a schema change that goes through `/decide` and an ADR. | R1 | Open |
| G45 | 16 | T8.1, T16.5 | `apply_event` runs T16's side effects inside the order's database transaction, and one of them calls `provider.refund`. If a later step of the same transaction fails (saving the payment or the order), the database rolls back but the provider's refund stays. A retry of the cancellation then refunds again, unless the real provider treats the call as idempotent. The mock hides this. | Before the refund goes live (T16.5), send the provider an idempotency key derived from the payment (for example `refund:<payment id>`), or record the refund attempt before calling the provider and skip a payment that already has one. Check which of the two Mercado Pago's refunds API supports. | R1 | Open |
| G46 | 9 | T8.13, T9.8 | T17 and T18 say "Set `refunded_cents` on payment" and `_effects_refund` stores the `refunded_cents` value the caller passes. 8.A does not say whether that value is the running total or only the new refund. If T9.8 passes the new amount, a second partial refund overwrites the first and the payment under-reports what was returned. | T9.8 passes the running total (the payment's current `refunded_cents` plus the new amount), and the guards compare that total with `amount_cents`. A test issues two partial refunds in a row and checks the total after each. Built in T9.8. | R1 | Resolved (ADR-0048) |
| G47 | 13 | T6.7b, T8.6a, T8.5 | The Phase 8 review found three small defects, none of which breaks a Verify ID. (1) `OrderLookupView` compares the email exactly, so a guest who types it with other capitals than at checkout gets "No encontramos ese pedido", and the miss counts toward the 5-per-hour limit. (2) `advance_orders` catches only `IllegalTransition`, so one unexpected error on an order stops the run for the orders after it. (3) `partially_refunded` is still listed in `COUNTED_STATES` of `purchase_limits.py`, though G26 (ADR-0043) says no order is in that state. | Before the storefront lookup page is built (Phase 13): compare with `email__iexact`; catch and log any exception per order in `advance_orders`, as `expire_reservations` does; drop the dead entry. Add a test for each. A small fix task, or part of the next task that touches these files. | R1 | Open |
| G48 | 9 | T8.6a, T9.5 | `expire_reservations` picks orders by the hold's expiry but T5 only passes when `payment_deadline_at` is in the past. Today both come from the same card window. T9.5 gives payment methods different deadlines; a hold that lapses before its order's deadline makes the job raise `GuardFailed` and log a stack trace for that order every 5 minutes, and the hold stays. | In T9.5, set the hold length so it never ends before the order's `payment_deadline_at`, and have `expire_reservations` log a `GuardFailed` as a one-line warning instead of an exception. Add a test with a method whose deadline is longer than the card window. | R1 | Resolved (ADR-0050) |

#### Design System requests (DSR)

Each item is built in the DS repository under its own SPEC and released as a DS minor version (OA-09). This spec then raises the pinned version (A17) in a DS upgrade task. A name must avoid the DS's forbidden domain terms, such as "price", "cart" or "product" (DS:REQ-022).

| ID | Request | Needed by | Release | Status |
|---|---|---|---|---|
| DSR-01 | A generic slot in `CnMediaCard`, under the title, for a price and an availability badge | Phase 12 (product card) | R1 | Open |
| DSR-02 | A key-value list for attributes | Phase 12 (product page) | R1 | Open |
| DSR-03 | An image gallery, for example Nuxt UI's carousel themed by the DS | Phase 12 (product page) | R1 | Open |
| DSR-04 | Rows inside the email card, for order lines and totals | Phase 11 | R1 | Open |
| DSR-05 | A raster logo for the email `{{ logo_url }}` slot. The DS ships SVG only, and most email clients don't render SVG. | Phase 11 | R1 | Open |
| DSR-06 | `color-scheme: dark` and a `theme-color` meta. The layer doesn't set them in its own files; if Nuxt UI doesn't either, the DS adds them. | Phase 12 | R1 | Open |
| DSR-07 | The scope of the photo rule "no text inside the image" for product packaging (C-10) | Phase 12 | R1 | Open |
| DSR-08 | An order timeline | Phase 14 | R2 | Deferred (R2) |
| DSR-09 | Make the raw-value lint rule of DS:REQ-016 available to consuming apps, so the storefront runs the same check as the DS. Until then, P12-V26 is the storefront's check. | Phase 12 | R1 | Open |
| DSR-10 | `CnMediaCard.vue` (DS 1.0.0, line 81) fails `vue-tsc` with TS2352: `EventTarget \| null` converted to `Picture`. Found in T1.5 with `nuxt typecheck`; `make test` runs `vue-tsc`. | Phase 1 (T1.17) | R1 | Resolved (DS 1.0.1, T1.17) |

### 2.5 Dev defaults

These stand-ins let Part A run without waiting on business decisions. **Every value here must be replaced before production.** Seeded names start with `[PLACEHOLDER]`. `manage.py check_placeholders` exits non-zero while any of these remain: a `location`, `shipping_zone` or `shipping_rate` name with that marker; a product type whose `attribute_schema` carries `"$comment": "[PLACEHOLDER]"`; the CFDI catalog file while it carries the same comment; a `[DEMO]` row from the demo dataset (15.1); or a D6 or D7 setting still at its dev default. The launch checklist (Phase 22) requires it to exit 0.

| Decision | Placeholder | Applied via |
|---|---|---|
| D4 — warehouse | Location code `almacen`, name `[PLACEHOLDER] Almacén Cup Noobles`, `kind = 'warehouse'`, `is_pickup_point = false`, address `[PLACEHOLDER] Calle Ejemplo 123, Col. Centro, Cuauhtémoc, CMX 06000` | `manage.py seed_dev_defaults` |
| D5 — shipping | Zone `local` = CMX and MEX; zone `nacional` = the other 30 states. Rates named `[PLACEHOLDER] Envío estándar`: free at MXN 1,500 or more; otherwise MXN 99 local (1–3 days) and MXN 179 nacional (3–7 days). | `manage.py seed_dev_defaults` |
| D6 — OXXO and SPEI window | OXXO voucher 72 h plus 2 h grace; SPEI 4 h; card 30 min | `RESERVATION_TTL_OXXO_HOURS=72`, `RESERVATION_TTL_SPEI_HOURS=4` |
| D7 — meses sin intereses | 3 and 6 months, so the installments path is exercised by the mock | `PAYMENT_INSTALLMENT_OPTIONS=3,6` |
| D14 — product types | The plan's four launch types (`tcg_sealed`, `board_game`, `apparel`, `figure`) with their example schemas, plus `accessory` with an empty schema. Each schema carries the `[PLACEHOLDER]` comment. | The product-type seed (T2.8) |
| D16 — CFDI fields and codes | The CFDI 4.0 receptor fields as a stand-in list: RFC, name, fiscal postal code, régimen fiscal and uso de CFDI. Sample régimen and uso codes, with the `[PLACEHOLDER]` comment. The accountant confirms both. | `invoice_request` in `spec/schema.sql` (T2.1); `api/fixtures/cfdi_catalogs.json` |

The pickup hold period (`PICKUP_HOLD_DAYS`) leaves R1 with pickup.

### 2.6 Owner answers on record

| ID | Date | Question | Answer |
|---|---|---|---|
| OA-01 | 2026-10-11 | Has anything been built yet? | No. All tasks start as `[ ]`. |
| OA-02 | 2026-10-11 | How large should the requirements layer be? | No strong opinion; the owner leaves it to Claude. Chosen: phase deliverables and Verify tables stay the feature level, and §3 holds only cross-cutting REQs. |
| OA-03 | 2026-10-11 | What is the per-task gate? | CI runs the full suite on every push. Locally, each task runs a light suite, and the last task of each phase runs the full suite. |
| OA-04 | 2026-10-11 | Who approves what? | A team of one: the owner is the developer and the business owner. |
| OA-05 | 2026-10-19 | Should the DS be finished before the storefront's adoption is decided? | The DS is finished, at 1.0.0, and was evaluated before writing this spec. |
| OA-06 | 2026-10-19 | Is the guide's launch date a hard constraint? | Yes, but the spec carries no dates and focuses on the execution tasks. |
| OA-07 | 2026-10-19 | CFDI at launch? | The owner asked for a suggestion and accepted it: manual CFDI in R1 (A8). |
| OA-08 | 2026-10-19 | Is pickup offered? | No pickup in the first versions. |
| OA-09 | 2026-10-19 | When the storefront needs something the DS lacks? | Option A: the DS adds it first, as a minor release. |
| OA-10 | 2026-10-19 | The e-commerce repository? | Public, on GitHub Free, created by the owner. |
| OA-11 | 2026-10-19 | The launch cut (§1.2)? | Approved, with its two assumptions: no counter sales in R1, and customer accounts after R1. |
| OA-12 | 2026-10-19 | Defaults proposed by Claude | Not objected to: the plan's technology choices and decision log become accepted ADRs; the DS is pinned at exactly 1.0.0; `web/` uses pnpm; the spec is written in four stages. |
| OA-13 | 2026-10-19 | Which third-party skills to adopt? | The verdicts in §0.5 are accepted. |
| OA-14 | 2026-10-19 | Do you approve SPEC.md v0.4? | Approved. The spec becomes version 1.0, approved for Part A. |
| OA-15 | 2026-10-20 | Do the three private DS packages on GitHub Packages grant this repository read access (S8)? | Yes, already done. |
| OA-16 | 2026-10-20 | T1.3: which provider values does `prod.py` reject as mocks? | No strong opinion; follow Claude's suggestion: only `PAYMENT_PROVIDER=mock`, `CARRIER_PROVIDER=mock` and `EMAIL_PROVIDER=file`. `MEDIA_STORAGE=local`, `POSTAL_CODE_DATASET=sample` and `ERROR_TRACKING=off` stay accepted until Phases 18, 22 and 21, and the Phase 22 launch checklist makes them mandatory. |
| OA-17 | 2026-10-20 | T1.3: which apps does `INSTALLED_APPS` hold now? | No strong opinion; follow Claude's suggestion: keep it minimal, and each later task adds its own app. |
| OA-18 | 2026-10-20 | `/decide` slows execution. Which decisions still need it? | Option A: `/decide` only for owner-only decisions (business values, brand and visual choices, conflicts between SPEC, an ADR and a DS doc). The agent decides technical choices that change no requirement, Verify ID or business value, and lists them as "Judgment calls" in the task report. New gaps and DSR items are registered in §2.4 without an ADR; an ADR is written only for a choice costly to reverse. |
| OA-19 | 2026-10-20 | DS 1.0.1 fixes DSR-10. When is the pin raised? | Option A: a new task T1.17 right now, before T1.6. T1.8 depends on it. |
| OA-20 | 2026-10-21 | G1: `/api/health/` is verified in Phase 1 but specified only in 20.4. Where does the endpoint live? | Option A: the proposed resolution. T1.16 builds `GET /api/health/` in Phase 1; Phase 20 keeps only the Lightsail health-check configuration. |
| OA-21 | 2026-10-23 | G29: CI and branch protection are verified only in Phase 20. Where are they verified? | Option B: the proposed resolution, with the GitHub settings in force written into the record. P1-V23 is a `[manual]` item in Phase 1; ADR-0029 lists the settings. |
| OA-22 | 2026-10-23 | G28: how are featured and related products modelled? | Option A: the proposed resolution. `product.is_featured` and `featured_position`; related products are those sharing the franchise or a category. ADR-0030. |
| OA-23 | 2026-10-23 | G34: where does the bin location live? | Option A: the proposed resolution. An optional text field `stock_item.bin_location`, editable in the admin, shown on the packing view. ADR-0030. |
| OA-24 | 2026-10-23 | G3: where is the checkout idempotency key stored? | Option A: the proposed resolution. `idempotency_key` and a request fingerprint on `order`, unique per cart token; a mismatched body returns 422 `idempotency_key_reused`. ADR-0030. |
| OA-25 | 2026-10-23 | G5: which timezone gives the order-number year? | Option A: the proposed resolution. `America/Mexico_City` for numbering and display; one Postgres sequence per year, created on first use. ADR-0030. |
| OA-26 | 2026-10-23 | G31: how are purchase limits per customer enforced? | Option A: the proposed resolution. `variant.purchase_limit` set in the admin; the guard counts units in pending and paid orders matching the email, phone or normalised shipping address within a window. The owner gave no window length, so it stays in D15 and the setting `PURCHASE_LIMIT_WINDOW_DAYS` has no default. ADR-0030. |
| OA-27 | 2026-10-23 | G33: how is the unit cost captured for reports? | Option A: the proposed resolution. `order_line.unit_cost_cents` snapshotted at order creation, plus admin CSV exports. ADR-0030. |
| OA-28 | 2026-10-23 | G40: T2.1c found that Django 5.2 enforces the schema's `ON DELETE` rules in Python, not in the database. Enforce them in the database too? | Option A: accept as is. Only the four named foreign keys carry the exact rules; revisit on Django 6.0. ADR-0031. |
| OA-29 | 2026-10-23 | G41: T2.7 seeds the 32 states only through the dev command `seed_dev_defaults`. How does production load them? | Option A: the proposed resolution. A separate idempotent `manage.py seed_states` command, run by the deploy step; `seed_dev_defaults` keeps calling the same function. ADR-0032 |
| OA-30 | 2026-10-24 | Phase 3 task order: T3.1 generates slugs, but T3.2 (slugs) depended on T3.1. Reorder? | Option A: T3.2 runs first, then T3.1; the "Depends on" lines of T3.1, T3.2, T3.3 and T3.6 are fixed. No ADR: cheap to reverse, spec text only. |
| OA-31 | 2026-10-24 | G12: what does `import_catalog` do with the valid rows when some rows are invalid? | Option A: the proposed resolution. All or nothing per file, reporting every invalid row. ADR-0033. |
| OA-32 | 2026-10-24 | Phase 4 task order: T4.1 (`reserve`) raises `InsufficientStock`, which T4.2 defines, and the "Depends on" chain was otherwise arbitrary. Reorder? | Option A: T4.2 runs first, then T4.1, T4.3, T4.4, T4.9, T4.6, T4.7, T4.8 (phase-close); T4.10 and T4.5 stay R2. The "Depends on" lines of T4.1, T4.2, T4.3 and T4.8 are fixed. No ADR: cheap to reverse, spec text only. |
| OA-33 | 2026-10-24 | G24: where is `check_stock_integrity` built, given P4-V07 tests it in Phase 4 but 21.7 specified it? | Option A: the proposed resolution. The command is built in Phase 4 (T4.9); 21.7 is absorbed and keeps only the production schedule. ADR-0034. |
| OA-34 | 2026-10-25 | G20: how do staff receive goods in the admin? | Option A: the proposed resolution. A "Recibir mercancía" admin action (variant, location, quantity) calling `receive_stock` in R1, and `receive_preorder_stock` for pre-order variants in R2. ADR-0035. |
| OA-35 | 2026-10-25 | G2: where does the outbox write helper live? | Option A: the proposed resolution. `enqueue_email()` is built in Phase 4 (T4.6); it writes the row and does not send. ADR-0036. |
| OA-36 | 2026-10-25 | G15: is `commit_reservations` idempotent? | Option A: the proposed resolution. A second commit of committed reservations is a no-op. ADR-0036. |
| OA-37 | 2026-10-25 | G37: which job expires an unpaid order, and when does the order state change? | Option A: the proposed resolution. In Phase 4 `expire_reservations` releases lapsed holds only. From Phase 8 it fires T5 through `apply_event`, and `advance_orders` stops firing T5. ADR-0036. |
| OA-38 | 2026-10-25 | G38: which address receives the owner's alerts? | Option A: the proposed resolution. An `OWNER_ALERT_EMAIL` setting (§4.7): a `.test` address in development, the owner's monitored inbox in production. ADR-0036. |
| OA-39 | 2026-10-25 | Phase 5 task order: T5.1 filtered and reported by availability (T5.3) and by attributes (T5.2), and P5-V01 needed both. Reorder? | Option A: T5.3 runs first, then T5.1, T5.2, T5.4, T5.5, T5.6, T5.7 (phase-close); T5.8 stays R2. The facets endpoint and P5-V13 move from T5.1 to T5.2. The "Depends on" lines of T5.1, T5.2, T5.3 and T5.4 are fixed. No ADR: cheap to reverse, spec text only. |
| OA-40 | 2026-10-25 | G13 with D10: does `low_stock` include exactly 5 units, and does the storefront show counts? | Option A: the proposed resolution. `low_stock` when `1 <= available <= 5` (5 units shows `low_stock`); a low-stock badge and no raw counts. ADR-0037. |
| OA-41 | 2026-10-25 | G32: where does the pre-launch switch live, and what do anonymous catalog requests get while it is on? | Option A and X: a single-row `site_setting` table with a `prelaunch_mode` flag, edited in the admin, so staff go live without a deploy. While on, anonymous `/api/catalog/*` requests get `503` with `{"prelaunch": true}` and `Cache-Control: no-store`; a staff session gets the normal catalog with `Cache-Control: private`. ADR-0038. |
| OA-42 | 2026-10-25 | Phase 6 task order: T6.1 (R2) was listed first but depends on T6.2, and R1 and R2 tasks were interleaved. Reorder? | Option A: T6.2, T6.6 and T6.7b (phase-close) run first; then, in R2, T6.1, T6.3, T6.4, T6.5, T6.7a and T6.8. An execution-order note is added. No ADR: cheap to reverse, spec text only. |
| OA-43 | 2026-10-25 | G30: is the full SEPOMEX dataset a launch requirement, or optional? | Yes. The full dataset is a launch requirement; the sample stays for Part A (the proposed resolution). |
| OA-44 | 2026-10-25 | G35: does the guest order lookup send the email in the URL (`GET`) or in a JSON body (`POST`)? | Option A: the proposed resolution. `POST /api/orders/lookup/` with the JSON body `{number, email}`, limited to 5 per hour per IP, and the same 404 for a wrong email and a missing order. |
| OA-45 | 2026-10-25 | Phase 7 task order: the tasks are listed in a valid order, but their numbers do not follow it and the phase has no execution-order note. Add one? | Option A: add the note. Execution order: T7.9, T7.7, T7.2a, T7.1, T7.3, T7.4, T7.6, T7.5a, T7.8 (phase-close); then, in R2, T7.2b and T7.5b. IDs keep their numbers. No ADR: cheap to reverse, spec text only. |
| OA-46 | 2026-10-25 | G44: should the cart store the postal code, or does the quote keep reading it from the request? | Keep the `postal_code` query parameter on `GET /api/cart/` for now, and check it in Phase 13. Registered as G44; no ADR, because the choice is cheap to reverse until then. |
| OA-47 | 2026-10-25 | Phase 8 task order: the tasks are listed in a valid order, but their numbers do not follow it (T8.2 needs T8.3 and T8.10; T8.5 runs near the end) and the phase has no execution-order note. Add one? | Option A: add the note. Execution order: T8.1, T8.3, T8.10, T8.2, T8.4, T8.7, T8.8, T8.9, T8.5, T8.6a (phase-close); then, in R2, T8.11 and T8.6b. IDs keep their numbers. No ADR: cheap to reverse, spec text only. |
| OA-48 | 2026-10-25 | G25: Phase 8 needs a payment provider (`create_checkout`, `refund`) before the mock exists. Resolve it now, or keep it open with an `xfail`? | Option A: the proposed resolution. The two `MockPaymentProvider` methods are built in Phase 8 (T8.10), and the rest of the mock in Phase 9 (T9.9). The tests of T8.10 and T8.2 are plain tests, with no `xfail`. ADR-0041. |
| OA-53 | 2026-10-26 | G7 and G8: how many times is a failing webhook row retried, and how are future timestamps and clock skew treated? | Option A for both: the proposed resolutions. G7: 10 attempts with exponential backoff, then the row is marked failed and an alert is raised. G8: a timestamp is accepted when `abs(now − ts) ≤ WEBHOOK_MAX_AGE_SECONDS`, so a future timestamp beyond that is rejected too. The tests of P9-V10, P9-V13 and P9-V17 are plain tests, with no `xfail`. ADR-0044. |
| OA-54 | 2026-10-26 | `WEBHOOK_INLINE_BUDGET_MS`: T9.3 shipped 2000 ms; should that be the value recorded in §4.7? | Yes: 2000 ms in Part A and Part B, and the §4.7 row says so. ADR-0045. |
| OA-55 | 2026-10-26 | G11: an OXXO or SPEI voucher can be generated after the card hold has lapsed and the order is `expired`. Alert only, cancel the voucher, or hold stock longer? | Option A, as the proposal reads minus its first half: the notification alerts a person and the voucher is cancelled at the provider; the order stays `expired`. No separate checkout-session TTL: T1 keeps the 30-minute card hold. The work is a new task, T9.15 (`cancel_payment`), run after T9.6. |
| OA-56 | 2026-10-26 | G14: a webhook and `reconcile_payments` process one approval at the same time; should the second be an error, or a no-op? | Accept the proposal: the second is treated as `webhook_no_op` when the order already reflects the status. T9.4's mapping already behaves this way, so no code changes. |
| OA-57 | 2026-10-26 | G46: is the `refunded_cents` a refund sets the payment's running total, or only the new refund? | Option A: the proposed resolution. The running total (the payment's current `refunded_cents` plus the new amount), and the guards compare that total with `amount_cents`. ADR-0048. |
| OA-58 | 2026-10-26 | When does the cart count as converted (`cart.converted_order`), the Phase 9 question left open since T8.4? | Option A: at T1 (checkout), in the same transaction as the order, as G22 proposes. A second checkout from that cart is refused; a repeat with the same `Idempotency-Key` still returns the original order. New task T9.16. Recorded for the cart half of G22 only; its pay-retry endpoint stays open until Phase 13. ADR-0049. |
| OA-59 | 2026-10-26 | G48: a reservation could lapse before its order's `payment_deadline_at` once payment methods have different deadlines. Resolve it as proposed? | Option A: the proposed resolution. A reservation never expires before its order's `payment_deadline_at`; both are extended together in one transaction, and `expire_reservations` logs a `GuardFailed` from T5 as a one-line warning. A test uses a method whose deadline is longer than the card window. T9.5 built it as written. ADR-0050. |
| OA-49 | 2026-10-25 | G4: what happens when a price changes between the last cart view and "Pagar"? | Option A: the proposed resolution. Checkout takes an optional `expected_total_cents`; a mismatch returns 409 `total_changed` with the fresh totals, creates no order and reserves nothing. Built by the new task T8.12. ADR-0042. |
| OA-50 | 2026-10-25 | G26: after a partial refund (T18), what happens to the order? | Option A: the proposed resolution. A partial refund is recorded on the payment and the order keeps its state, so it stays fulfillable. ADR-0043. |
| OA-51 | 2026-10-25 | G27: can a refund be recorded after the order is `completed`, `expired` or `cancelled`? | Option A: the proposed resolution. The refund events are accepted from those three states as recorded payment events: an `order_event` row and the payment's `refunded_cents`, with the order state unchanged. ADR-0043. |
| OA-52 | 2026-10-26 | Phase 9 task order: the tasks are listed in a valid order, but their numbers do not follow it (T9.9 runs third, T9.14 tenth) and earlier tasks mention later ones. Renumber, or add an execution-order note? | Option B: add the note, no renumbering. IDs keep their numbers. The note says the forward mentions are not dependencies. No ADR: cheap to reverse, spec text only. |

---

## 3. Requirements

Each phase's deliverable and Verify table (§6) are the feature-level requirements. This section holds what they can't express alone: invariants that span several phases, and the Release 1 features added by this conversion, whose work also spans phases (OA-02).

The acceptance criteria of a requirement are Verify IDs. The assertion text lives only in the Verify row, never here. ⚠️ G# marks a test written against a gap's proposed resolution and marked `xfail(strict=True, reason="G#")` until the gap is resolved (§2.4). `[R2]` marks a criterion that belongs to Release 2.

### 3.1 Money and pricing

| REQ | Requirement | Rules | Acceptance | Release |
|---|---|---|---|---|
| REQ-001 | Money is integer centavos of MXN everywhere: database, services, API and the conversion to a provider's pesos. | CR-01 | P2-V04 · P2-V10 · P7-V17 · P9-V08 · P12-V09 | R1 |
| REQ-002 | The server computes every total, in one function, from prices frozen once when the order is created. The client renders totals and never computes them. | CR-02, CR-03, A2 | P7-V03 · P7-V06 · P7-V17 · P8-V09 · P13-V03 · P13-V19 | R1 |

### 3.2 Inventory

| REQ | Requirement | Rules | Acceptance | Release |
|---|---|---|---|---|
| REQ-010 | Stock is never oversold, under any interleaving of checkouts, payments and expiries. | CR-04, CR-06, CR-07 | P2-V02 · P4-V01 · P4-V09 · P4-V11 · P8-V04 · P8-V10 · P8-V11 · P13-V18 · P15-V08. Counter sales `[R2]`: P4-V04 · P4-V14 | R1 |
| REQ-011 | Every change to physical stock is in the ledger, and the ledger sums to `on_hand`. | CR-05 | P1-V05 · P4-V02 · P4-V06 · P4-V07 · P4-V12 · P4-V15 · P4-V18 | R1 |
| REQ-012 | Stock held for an unpaid order is released at its deadline, exactly once, with no ledger row. | — | P4-V03 · P4-V05 · P4-V08 · P9-V09 · P15-V04 | R1 |
| REQ-013 | Pre-orders never touch shelf stock and never exceed their limit. | CR-08 | P2-V08 · P10-V07 · P10-V14 · P10-V15 · P10-V22 | R2 |

### 3.3 Orders and scheduled jobs

| REQ | Requirement | Rules | Acceptance | Release |
|---|---|---|---|---|
| REQ-020 | Every order state change goes through `apply_event` under a row lock and writes exactly one `order_event`. Anything outside the 8.A table is rejected. | CR-09, CR-10 | P1-V05 · P8-V01 · P8-V02 · P8-V05 · P8-V07 · P8-V15 | R1 |
| REQ-021 | Checkout is atomic and safe to repeat: one request, or many identical ones, creates at most one order and one set of reservations. | — | P8-V03 · P8-V08 · P8-V10 · P8-V18 · P9-V23 · P13-V02 · P13-V21 · P15-V08 | R1 |
| REQ-022 | Every scheduled job is idempotent and safe to run concurrently with itself and with webhook processing. | §4.8 | P4-V05 · P8-V14 · P9-V14 · P10-V19 · P11-V10 ⚠️G17 | R1 |

### 3.4 Payments

| REQ | Requirement | Rules | Acceptance | Release |
|---|---|---|---|---|
| REQ-030 | An order changes on payment only through a verified notification, a status fetched from the provider, and a matching amount. | CR-11 to CR-17 | P2-V16 · P9-V01 (PAY-01 to PAY-19) · P9-V05 · P9-V07 · P9-V10 · P9-V11 · P9-V12 · P9-V20 | R1 |
| REQ-031 | A lost notification is recovered by reconciliation, and a late one causes no second transition. | CR-15, CR-16 | P9-V04 · P9-V13 · P9-V14 · P9-V17 | R1 |
| REQ-032 | Refunds never exceed what was paid. A cash refund is recorded by hand, with a note. | — | P2-V13 · P8-V06 · P9-V15 · P9-V16 | R1 |

### 3.5 Integration boundaries

| REQ | Requirement | Rules | Acceptance | Release |
|---|---|---|---|---|
| REQ-040 | Vendor code stays in its adapter, and no mock or dev tool can run in production. | CR-18 to CR-21, CR-23 | P1-V12 · P1-V14 · P1-V15 · P1-V16 · P1-V19 · P9-V03 · P9-V06 · P10-V04 · P15-V11 | R1 |
| REQ-041 | Each mock and its real provider pass the same contract suite. | CR-22, A14 | P9-V01 · P10-V01 · P16-V01 · P19-V01 | R1 |
| REQ-042 | Part A makes no outbound connection, proven from a clean clone on an internal network. | CR-41, A13 | P1-V08 · P1-V13 · P15-V13 · P15-V14 | R1 |

### 3.6 Storefront, email and the Design System

| REQ | Requirement | Rules | Acceptance | Release |
|---|---|---|---|---|
| REQ-050 | The storefront is assembled from the Design System layer at a pinned version, and adds no visual styling of its own. | CR-26, CR-27, CR-34, CR-46 | P12-V26 · P12-V27 | R1 |
| REQ-051 | Every storefront page meets WCAG 2.2 AA, works at 360 px wide, and has tap targets of at least 44 px. | CR-33, CR-35, CR-36 | P1-V09 · P1-V20 · P12-V12 · P12-V19 · P12-V21 · P13-V16 · P14-V17 · P15-V01 · P15-V03 · P15-V04 · P15-V08 | R1 |
| REQ-052 | Customer-facing text, money and dates are es-MX and follow the DS voice, microcopy and formatting rules. | CR-30, CR-31, CR-32 | P11-V04 · P12-V09 · P12-V12 · P13-V14 ⚠️G21 | R1 |
| REQ-053 | The storefront renders on the server and never shows a blank page: a failed call offers a retry, and an unknown URL is a real 404. | — | P12-V01 ⚠️G18 · P12-V03 · P12-V20 · P12-V25 ⚠️G18 · P13-V20 | R1 |
| REQ-054 | A change to the API contract fails the build until the generated client and the code that uses it are updated. | CR-25, CR-29 | P1-V07 · P5-V04 · P12-V04 · P12-V24 | R1 |
| REQ-055 | Transactional emails are built only from the DS email components at the pinned version, each with a complete plain-text part. | CR-32, CR-46 | P11-V01 · P11-V12 · P11-V13 | R1 |

### 3.7 Release 1 operations

These come from the owner's execution guide (§1.2). Their mechanisms are proposals in §2.4 until the owner decides, except manual CFDI, which is decided (OA-07).

| REQ | Requirement | Rules | Acceptance | Release |
|---|---|---|---|---|
| REQ-060 | A customer can request a CFDI at checkout. Staff issue it outside the store and record it, and the store emails the PDF and XML. A refund of an invoiced order is flagged for the accountant, and an export covers the orders a global invoice needs. | A8, A12, D16 | P2-V17 · P8-V19 · P9-V22 · P10-V23 · P10-V24 · P11-V11 · P13-V23 · P15-V15 | R1 |
| REQ-061 | A variant's purchase limit holds per customer, across guest orders. | D15 | P8-V20 · P13-V24 | R1 |
| REQ-062 | Before launch, the public sees only a "próximamente" page while staff browse and buy for real. Going live is one switch. | — | P5-V15 · P12-V28 · P15-V16 | R1 |
| REQ-063 | Staff can export what the weekly dashboard and the monthly report need, including each line's unit cost at the time of sale. | A19 | P8-V21 · P10-V25 | R1 |
| REQ-064 | Staff receive goods and see where each item is stored, from the admin, without editing stock by hand. | CR-05 | P4-V19 · P4-V20 · P10-V26 | R1 |
| REQ-065 | No placeholder, demo row or dev default reaches production. | CR-45, §2.5 | P2-V18 · P15-V12 · P22-V15 | R1 |

### 3.8 Quality gates

| REQ | Requirement | Rules | Acceptance | Release |
|---|---|---|---|---|
| REQ-070 | Every Verify ID of the release in progress maps to a passing test, and the register in §2.4 matches the code and tests. | CR-39 | P1-V10 · P1-V21 · P1-V22 | R1 |
| REQ-071 | Coverage meets its gates at phase close and never decreases. | CR-44 | P1-V06 | R1 |
| REQ-072 | Migrations produce exactly `spec/schema.sql`, on PostgreSQL only, and every migration reverses. | CR-40 | P1-V04 · P2-V01 · P2-V07 | R1 |
| REQ-073 | The full suite runs in CI on every push and pull request, and a red run blocks merging. | CR-37 | P1-V03 · P1-V23 · P15-V14 | R1 |

## 4. Technical design

This section holds the design that spans phases. Design that belongs to one phase stays inside it in §6, under its plan number: the order state machine (8.A), the payment ground rules (9.A), the stock paths (10.A), and the page tables (12.A, 13.A, 14.A).

### 4.1 Architecture

The same code runs in two modes. Only the adapter layer differs (§4.3): Part A wires every boundary to a mock, and Part B wires it to the real provider. Everything above the adapter layer, and every Part A test, is identical in both.

**Part A — local mode.** Runs under `docker compose`. The project network is internal, so nothing reaches the internet (15.5).

```text
  Browser / Playwright (e2e service)
        │
        ▼
  ┌─────────────┐   /api /admin /static /media /dev   ┌───────────────────────────────────────────┐
  │    proxy    │ ──────────────────────────────────► │ api — Django + DRF                        │
  │   (Caddy)   │                                     │                                           │
  │             │   /*     ┌──────────────┐           │  catalog · inventory · orders · payments  │
  │             │ ───────► │ web — Nuxt   │ ── SSR ──►│  shipping · invoicing · notifications     │
  └─────────────┘          │ SSR + DS     │   fetch   │                  │                        │
                           │ layer (G18)  │           │     apps/core/providers.py (§4.3)          │
                           └──────────────┘           │ ═══════ adapter layer: mocks ════════════ │
                                                      │  MockPaymentProvider   MockCarrier         │
                                                      │  FileEmailSender       FileSystemStorage   │
                                                      │  DbPostalCodeLookup    NullErrorReporter   │
                                                      │  ManualInvoicer                            │
                                                      └─────┬──────────────────┬──────────────────┘
                                                            │                  │
                                         ┌──────────────────▼──┐   ┌───────────▼──────────────────┐
                                         │ db — Postgres 16    │   │ var/ (bind mount)            │
                                         │ source of truth,    │   │ mocks/  emails/  media/      │
                                         │ sample postal codes │   │ e2e/manifest.json            │
                                         └─────────────────────┘   └──────────────────────────────┘

  mock-webhooks — signs queued notifications → POST /api/webhooks/payments/mock/ (9.11)
  scheduler     — runs the §4.8 management commands from infra/crontab
```

**Part B — production.** AWS Lightsail (Phase 20).

```text
  Customer ──► CDN ──► ┌─ Lightsail container service ──────────────────────────────────┐
                       │  proxy (Caddy) ──► web (Nuxt SSR + DS layer)                   │
                       │        └─────────► api (Django + DRF)                          │
                       │                     domain → apps/core/providers.py            │
                       │  scheduler (G23)                                               │
                       │  ════════ adapter layer: real providers ═════════════════════  │
                       │  MercadoPagoProvider   ManualCarrier (no API, A7)              │
                       │  Resend / SES sender   S3 storage (django-storages)            │
                       │  DbPostalCodeLookup (full SEPOMEX)   SentryErrorReporter       │
                       │  ManualInvoicer (no PAC, A8)                                   │
                       └───────┬───────────────┬────────────────┬───────────────┬───────┘
                               ▼               ▼                ▼               ▼
                     Managed Postgres   Object Storage    Mercado Pago     Resend / SES,
                     (source of truth)  (images via CDN)  (webhooks back   Sentry
                                                           to /api/webhooks/payments/mercadopago/)
```

Four structural decisions carry the design:

1. **One origin.** Caddy fronts both apps: `/api/*` goes to Django, everything else to Nuxt. This removes CORS, JWT and token refresh, and makes authentication a plain Django session cookie (ADR-0010).
2. **The cart lives in the database.** The client holds only an opaque cart token in a cookie. There is no client-side cart, no localStorage sync, and no stale price (ADR-0011).
3. **Third-party services sit behind adapters.** Part A proves the business logic with no accounts, credentials or bills. Part B changes environment variables and adds adapters, not domain code (ADR-0016).
4. **The storefront owns no visual design.** Every component, token, font, icon and image rule comes from the Cup Noobles Design System at a pinned version (§4.5, ADR-0022).

### 4.2 Technology decisions

Each decision becomes an accepted ADR in T1.15 (OA-12). The plan's reasoning, including its comparisons in plan 3.1–3.5, goes into each ADR's context section. Dated prices go to Appendix C.

| ADR | Decision | Choice | Alternatives considered | Source |
|---|---|---|---|---|
| ADR-0001 | Baseline assumptions | A1–A19 (§2.3) | — | plan §1; OA-07, OA-08, OA-10, OA-11 |
| ADR-0002 | Dev defaults | Placeholders, never business values; `check_placeholders` gates launch (§2.5) | Waiting on decisions | plan §5.E |
| ADR-0003 | Database | PostgreSQL 16 with JSONB | MongoDB, MySQL | plan 3.1 |
| ADR-0004 | Attribute model | JSON Schema on `product_type`, JSONB on `product` | EAV tables; one table per category | plan 2.4, App. C |
| ADR-0005 | Backend | Django 5 + DRF; the admin is the back office | FastAPI, Go, Node/Medusa | plan 3.2 |
| ADR-0006 | Background work | Cron and management commands | Celery + Redis | plan 3.2 |
| ADR-0007 | Frontend | Nuxt 4 SSR extending the DS layer; pnpm | Vue SPA, Django templates; plain Nuxt UI | plan 3.3; C-01, C-02, C-11 |
| ADR-0008 | Client state | Server state only | Pinia | plan 3.3 rule 1 |
| ADR-0009 | API client | Generated from the OpenAPI snapshot | Hand-written | plan 3.3 rule 2 |
| ADR-0010 | Routing and auth | One origin through Caddy; session cookie | Separate domains, CORS, JWT | plan §2 |
| ADR-0011 | Cart | Server-side; prices not stored; frozen once at order creation | Client-side cart | plan 7.3 |
| ADR-0012 | Payments | Mercado Pago Checkout Pro behind `PaymentProvider` | Stripe, PayPal | plan 3.4 |
| ADR-0013 | Payment truth | Webhook plus reconciliation; idempotency on the delivery id | Redirect; idempotency on the payment id | plan 9.A |
| ADR-0014 | Pre-order stock | A separate counter on `variant` | Negative `on_hand` | plan 10.A |
| ADR-0015 | Hosting | AWS Lightsail; no staging at launch | ECS/RDS, Fly, Hetzner; a second environment | plan 3.5, 20.9 |
| ADR-0016 | Integrations | Mock-first adapters, one env var each; mock state outside the app database; one contract suite per boundary | Real sandboxes from the start; mock tables in the app database | plan §5, 9.9, 9.13 |
| ADR-0017 | Test discipline | PostgreSQL only; branch-coverage gates with a ratchet; Verify IDs traced to tests; offline clean-clone proof | SQLite; fixed thresholds; manual checklists | plan §6 |
| ADR-0018 | Per-task gate | `make test` per task, `make test-all` at phase close and in CI on every push | The full suite on every task | OA-03 |
| ADR-0019 | CFDI | Issued by hand in R1, behind `InvoiceProvider` with a manual implementation | A PAC integration; no CFDI | OA-07 |
| ADR-0020 | Release 1 scope | Delivery only, guest checkout, no counter sales, pre-orders in R2 (§1.2) | The plan's full v1 | OA-08, OA-11 |
| ADR-0021 | Repository | Public on GitHub Free; internal data stays out (CR-48) | Private with GitHub Pro | OA-10 |
| ADR-0022 | Design System adoption | Consume the layer and email package at an exact version; missing parts are DS requests | Styling in the storefront | OA-09, OA-12; DS:OD-01, DS:OD-11 |
| ADR-0023 | Agent skills | The §0.5 policy | Third-party plugins and always-on rule sets | OA-13 |
| ADR-0024 | Price format | The `Intl` output, no suffix (DS:formatting.md) | `$1,234.00 MXN` | G19, C-08 |
| ADR-0025 | Brand assets | Supplied by the DS; D11 resolved | Nuxt UI defaults | D11 |

### 4.3 Integration boundaries and mocks

Every third-party dependency sits behind an interface owned by this codebase. Each interface has a mock used in Part A and a real implementation added in Part B, chosen by one environment variable. The rules are CR-18 to CR-23.

Dev tools — the payment simulator (9.10), the mock tracking page (10.10), the `/dev/test/` endpoints (13.8, 15.3) and the mock and webhook management commands — are gated by `DEV_TOOLS_ENABLED`. `prod.py` forces it to false.

#### Interfaces

```python
# apps/payments/base.py — value types (NormalizedStatus, ProviderPayment, WebhookRef) in 9.1
class PaymentProvider(Protocol):
    code: str
    def create_checkout(self, order: Order) -> CheckoutSession: ...
    def fetch_payment(self, provider_payment_id: str) -> ProviderPayment: ...
    def find_payments(self, external_reference: str) -> list[ProviderPayment]: ...
    def refund(self, payment: Payment, amount_cents: int | None) -> RefundResult: ...
    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> WebhookRef | None: ...


# apps/shipping/carriers/base.py
@dataclass(frozen=True)
class ShipmentRef:
    carrier: str
    tracking_number: str
    tracking_url: str

class ShipmentStatus(StrEnum):
    UNKNOWN = "unknown"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    EXCEPTION = "exception"

class TrackingNumberRequired(Exception): ...   # raised by carriers that cannot generate one

class CarrierProvider(Protocol):
    code: str
    def create_shipment(self, order: Order, *, tracking_number: str | None = None) -> ShipmentRef: ...
    def get_status(self, tracking_number: str) -> ShipmentStatus: ...


# apps/notifications/email/base.py
@dataclass(frozen=True)
class Attachment:
    filename: str
    content_type: str
    content: bytes

@dataclass(frozen=True)
class OutgoingEmail:
    to: str
    subject: str
    html: str
    text: str
    template: str
    reply_to: str | None = None
    attachments: tuple[Attachment, ...] = ()   # the CFDI PDF and XML (REQ-060)

class EmailSendError(Exception): ...

class EmailSender(Protocol):
    def send(self, message: OutgoingEmail) -> str: ...   # provider message id; raises EmailSendError


# apps/invoicing/base.py
@dataclass(frozen=True)
class IssuedInvoice:
    cfdi_uuid: UUID
    folio: str
    pdf: bytes
    xml: bytes

class ManualIssueRequired(Exception): ...   # the manual invoicer: staff record the CFDI in the admin

class InvoiceProvider(Protocol):
    code: str
    def issue(self, request: InvoiceRequest) -> IssuedInvoice: ...


# apps/core/media.py — the only subset of Django's Storage API app code may use.
# Django storage backends satisfy this Protocol structurally.
class MediaStore(Protocol):
    def save(self, name: str, content: File) -> str: ...
    def url(self, name: str) -> str: ...
    def exists(self, name: str) -> bool: ...
    def delete(self, name: str) -> None: ...


# apps/shipping/postal.py
@dataclass(frozen=True)
class PostalCodeInfo:
    postal_code: str
    state_code: str
    state_name: str
    municipality: str
    neighborhoods: tuple[str, ...]

class PostalCodeLookup(Protocol):
    def lookup(self, postal_code: str) -> PostalCodeInfo | None: ...


# apps/core/errors/base.py
class ErrorReporter(Protocol):
    def capture_exception(self, exc: BaseException, **context: Any) -> None: ...
    def capture_message(self, message: str, *, level: str = "error", **context: Any) -> None: ...
```

The single place implementations are chosen:

```python
# apps/core/providers.py
PAYMENT_IMPLS = {"mock": "apps.payments.mock.MockPaymentProvider",
                 "mercadopago": "apps.payments.mercadopago.MercadoPagoProvider"}
CARRIER_IMPLS = {"mock": "apps.shipping.carriers.mock.MockCarrier",
                 "manual": "apps.shipping.carriers.manual.ManualCarrier"}
EMAIL_IMPLS   = {"file": "apps.notifications.email.file.FileEmailSender",
                 "resend": "apps.notifications.email.resend.ResendEmailSender",
                 "ses": "apps.notifications.email.ses.SesEmailSender"}
ERROR_IMPLS   = {"off": "apps.core.errors.null.NullErrorReporter",
                 "sentry": "apps.core.errors.sentry.SentryErrorReporter"}
INVOICE_IMPLS = {"manual": "apps.invoicing.manual.ManualInvoicer"}

@cache
def payment_provider() -> PaymentProvider: return _load("PAYMENT_PROVIDER", PAYMENT_IMPLS)
@cache
def carrier() -> CarrierProvider:         return _load("CARRIER_PROVIDER", CARRIER_IMPLS)
@cache
def email_sender() -> EmailSender:        return _load("EMAIL_PROVIDER", EMAIL_IMPLS)
@cache
def error_reporter() -> ErrorReporter:    return _load("ERROR_TRACKING", ERROR_IMPLS)
@cache
def invoicer() -> InvoiceProvider:        return _load("INVOICE_PROVIDER", INVOICE_IMPLS)
def postal_code_lookup() -> PostalCodeLookup: return DbPostalCodeLookup()
def media_store() -> MediaStore:          return default_storage

def _load(setting: str, impls: dict[str, str]):
    value = getattr(settings, setting)
    if value not in impls:
        raise ImproperlyConfigured(f"{setting}={value!r}; expected one of {sorted(impls)}")
    return import_string(impls[value])()
```

A pytest fixture, `use_provider(setting, value)`, applies `override_settings` and calls `cache_clear()`, so a test can switch implementations without leaking state into other tests.

#### Boundaries

| Boundary | Env var and values | Part A | Part B | Behaviour |
|---|---|---|---|---|
| Payments | `PAYMENT_PROVIDER=mock\|mercadopago` | `apps/payments/mock.py` → `MockPaymentProvider` | `apps/payments/mercadopago.py` (Phase 16) | A local simulator page (9.10). HMAC-signed notifications, signed with `MOCK_PAYMENT_WEBHOOK_SECRET`, delivered to the real endpoint `/api/webhooks/payments/mock/`. State in a JSON store under `MOCK_STORE_DIR`. Full specification: 9.9–9.13. |
| Carrier | `CARRIER_PROVIDER=mock\|manual` | `apps/shipping/carriers/mock.py` → `MockCarrier` | `apps/shipping/carriers/manual.py` (Phase 19): staff enter the tracking number; the URL comes from a per-carrier template. No carrier API (A7). | Deterministic tracking numbers `MOCK-<order number>-<n>`; `tracking_url` points at a local dev-only page. `get_status` returns whatever the tracking page or `mock_carrier advance` last set. Full specification: 10.9–10.13. |
| Email | `EMAIL_PROVIDER=file\|resend\|ses` | `apps/notifications/email/file.py` → `FileEmailSender` | `resend.py` or `ses.py` in the same package (Phase 17) | Writes `<EMAIL_FILE_DIR>/<YYYYmmdd-HHMMSS>-<template>-<outbox id>.html`, a matching `.txt`, and each attachment as `<same prefix>-<filename>`. `EMAIL_FILE_DIR` defaults to `var/emails/`. `EMAIL_MOCK_FAIL=1` makes every send raise `EmailSendError`, for testing outbox retries. |
| Media storage | `MEDIA_STORAGE=local\|s3` | Django `FileSystemStorage`, `MEDIA_ROOT=var/media/`, served at `/media/` by Django in `DEBUG` | `django-storages` S3 backend against Lightsail Object Storage (Phase 18) | Plain files on disk. The backend is named as a dotted string in `STORAGES`, so `storages` and `boto3` are never imported by app code. `@nuxt/image` uses the `none` provider in Part A and the CDN provider from 18.3. CFDI documents never go here (§4.4). |
| Postal codes | `POSTAL_CODE_DATASET=sample\|sepomex` (read by `manage.py load_postal_codes`) | `api/fixtures/mx_postal_codes_sample.csv`: about 40 postal codes across at least 6 states (CMX, MEX, JAL, NLE, YUC, PUE), including every one the test suite uses (06700, 97000) | The full SEPOMEX dataset from a manually downloaded file path; the loader never makes a network call (G30) | The runtime lookup is always `DbPostalCodeLookup` reading `mx_postal_code`; only the loaded data differs. The sample file is headed `SAMPLE — not authoritative`. Colonia names need not be exact, but each code's `state_code` must be correct, because the shipping zone depends on it. |
| Error tracking | `ERROR_TRACKING=off\|sentry` (api), `NUXT_PUBLIC_ERROR_TRACKING=off\|sentry` (web) | `apps/core/errors/null.py` → `NullErrorReporter`, which logs to stdout. Web: no Sentry module registered. | `apps/core/errors/sentry.py` (Phase 21). Web: `@sentry/nuxt` registered in `nuxt.config.ts` only when the value is `sentry`. | Logs the exception and its context at ERROR. It never initialises an SDK or opens a socket. |
| Invoicing | `INVOICE_PROVIDER=manual` | `apps/invoicing/manual.py` → `ManualInvoicer` | The same. A PAC adapter is added only if the owner decides (R2 or later). | `issue()` raises `ManualIssueRequired`; the admin then requires the folio, UUID, PDF and XML (P10-V23). It is not a mock: `prod.py` accepts it. |

#### Enforcement

These are tests, written in Phase 1 and run by `make test`.

`tests/architecture/test_vendor_imports.py` parses every `.py` file under `api/apps` and `api/config` with `ast`, collects each top-level imported package, and fails if a vendor package is imported outside its allowlisted modules:

```python
VENDOR_ALLOWLIST = {
    "mercadopago": {"apps/payments/mercadopago.py"},
    "resend":      {"apps/notifications/email/resend.py"},
    "boto3":       {"apps/notifications/email/ses.py"},
    "botocore":    {"apps/notifications/email/ses.py"},
    "storages":    set(),   # referenced only as a dotted string in STORAGES
    "sentry_sdk":  {"apps/core/errors/sentry.py"},
    "requests":    {"apps/payments/mercadopago.py"},
    "httpx":       {"apps/payments/mercadopago.py"},
}
```

`tests/architecture/test_provider_selection.py` fails in three cases:

- Any module other than `apps/core/providers.py` (and tests) imports an implementation module: `*.mock`, `*.mercadopago`, `*.manual`, `*.file`, `*.resend`, `*.ses`, `*.null` or `*.sentry` under the adapter packages.
- `prod.py` accepts a mock value.
- An unknown value doesn't raise `ImproperlyConfigured`.

Offline guarantee: the whole Part A backend suite runs under `pytest-socket` with `--disable-socket --allow-hosts=127.0.0.1,localhost,db`. Any attempt to reach the internet fails the test that made it.

Frontend: an ESLint `no-restricted-imports` rule allows `@sentry/*` only in `nuxt.config.ts`.

### 4.4 Data model

The canonical schema is **`spec/schema.sql`**, a normative part of this spec. Django models are the source of truth in code; the schema file is what they must produce. P2-V01 parses it and compares it with `pg_catalog` after `migrate`, and fails on any table beyond it. It changes only under the amendment rule (§8).

Two kinds of protection live in the schema and must not be skipped (2.2): `CHECK` constraints and partial unique indexes stop an oversell or a wrong total even when application code has a bug; generated columns and GIN indexes make search and attribute filters fast.

**The attribute-agnostic catalog.** A `product_type` stores a JSON Schema for its products' attributes, the axes its variants vary along, and the attribute keys shown as filters. A product stores its attributes as JSONB, validated against that schema. Adding a category is an `INSERT`, not a migration:

```sql
INSERT INTO product_type (code, name, attribute_schema, variant_axes, filterable_keys) VALUES (
  'funko', 'Funko Pop',
  '{"type":"object","additionalProperties":false,
    "required":["linea","numero"],
    "properties":{
      "linea":   {"type":"string","title":"Línea"},
      "numero":  {"type":"integer","title":"Número"},
      "exclusivo":{"type":"string","title":"Exclusivo de"},
      "chase":   {"type":"boolean","title":"Chase"}}}'::jsonb,
  '[]'::jsonb,
  '["linea","exclusivo","chase"]'::jsonb
);
```

The admin form, the storefront filters and the API validation all read `attribute_schema` at runtime.

**Changes from the plan's DDL.**

- New tables `invoice_request` and `invoice_document` for manual CFDI (A8, ADR-0019). The PDF and XML are stored in the database, not in public media storage, because they hold the customer's fiscal data. An issued request has one document of each kind; the service enforces that (P10-V23).
- Comments only: the location code is `almacen` (D4, CR-47), and the launch product types follow D14.
- Release 1 additions decided after the plan (ADR-0030): `product.is_featured` and `featured_position` (G28); `stock_item.bin_location` (G34); `order.cart_token`, `idempotency_key` and `idempotency_fingerprint` with the unique index `order_idempotency_uq` (G3); `variant.purchase_limit` (G31); `order_line.unit_cost_cents` (G33). The per-year order-number sequences (G5) are database objects the service creates on first use; they are not in the DDL.

**Tables kept but unused in Release 1.** They stay so a later release needs no migration: `in_store_sale` and `in_store_sale_line` (counter sales), `address` (customer accounts), and the pickup and pre-order columns on `location`, `variant`, `cart`, `order`, `order_line` and `inventory_reservation`. `customer` is used in R1, because it is Django's user model and staff sign in to the admin with it.

**CFDI catalog codes.** The régimen fiscal and uso de CFDI codes offered at checkout come from `api/fixtures/cfdi_catalogs.json`. Until the accountant confirms the subset (D16), the file holds sample codes and the `[PLACEHOLDER]` comment, so `check_placeholders` fails (§2.5). The RFC format is checked in the application, not in the schema.

**Pending schema changes.** Only G36 is pending, and it is Release 2. The Release 1 items G3, G5, G28, G31, G33 and G34 were decided before Phase 2 (ADR-0030) and are in `spec/schema.sql`.

| Item | Proposed change | Release |
|---|---|---|
| G36 | `variant.preorder_closes_at` | R2 |

### 4.5 Storefront and the Design System

**Packages.** `web/` consumes the three DS packages at one exact version, currently `1.0.1` (A17):

| Package | What the storefront uses | Where |
|---|---|---|
| `@vinsmokemau/cup-noobles-nuxt` | The Nuxt layer: Nuxt UI 4.11.2 themed by the tokens, Tailwind 4.3.3, the `Cn*` components, the Phosphor Bold icon set, self-hosted Titan One and Rubik, forced dark mode | `extends` in `nuxt.config.ts` |
| `@vinsmokemau/cup-noobles-tokens` | Brought in by the layer. The storefront never reads a token directly. | — |
| `@vinsmokemau/cup-noobles-email` | The compiled email components and reference layout, vendored into the API (below) | `api/apps/notifications/templates/email/ds/` |

The storefront pins Nuxt to the version of the DS consumer fixture (4.5.2) and adds its own non-visual modules: `@nuxt/image`, `@nuxtjs/sitemap` and `zod`. It does not install `@nuxt/ui` or `tailwindcss` itself (P12-V27). A DS upgrade is its own task, which changes the pinned version, refreshes the vendored email HTML, and runs `make test-all`.

**Install and access.** The packages are private on GitHub Packages (DS:OD-03), so every install needs a token (S8). The steps follow DS:using-the-system.md:

- `web/.npmrc` is committed and holds only `@vinsmokemau:registry=https://npm.pkg.github.com`.
- Locally, the token line `//npm.pkg.github.com/:_authToken=${NODE_AUTH_TOKEN}` goes in the user-level `~/.npmrc`, never in the repository.
- In CI, `actions/setup-node` with `registry-url: https://npm.pkg.github.com` and `scope: '@vinsmokemau'` writes that line, and the install step receives `NODE_AUTH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` with `permissions: packages: read`. Each DS package grants this repository Actions read access.
- `pnpm-workspace.yaml` sets `allowBuilds: { esbuild: false, vue-demi: false }`.
- Image builds receive the token as a build secret, never as a build argument or a layer.

**Offline.** Fonts, icons and brand SVGs ship inside the layer package, so nothing is fetched at run time (`ui.fonts: false` in the layer). Images are built before the network turns internal (15.5), so the offline proof (P15-V14) holds.

**Consumption rules.** CR-26, CR-27, CR-32 to CR-36. In practice:

- Layout uses Tailwind utilities only: display, flex and grid, gap, spacing, sizing, position and overflow. No color, border, radius, shadow, ring, font or arbitrary-value utility, and no `style` with a visual value (P12-V26).
- There is no storefront `main.css`, and `app.config.ts` does not override `ui.colors` or `ui.icons`.
- Component props choose the DS-approved variants and sizes; a 44 px tap target is reached with size props (CR-36).
- The raw-value lint rule of DS:REQ-016 runs on `web/` once the DS publishes it (DSR-09). Until then, P12-V26 is the check.

**Composition map.** Storefront components keep plain names; the `Cn` prefix belongs to the DS (DS:REQ-021).

| Storefront component (task) | DS parts | DS request |
|---|---|---|
| ProductCard (12.4) | `CnMediaCard`, badge | DSR-01: a slot for price and availability |
| AvailabilityBadge (12.4) | badge; the status is in the text, not the color (P12-V12) | — |
| VariantSelector (12.4) | radio group | — |
| FilterSidebar (12.4) | checkbox, form field; slideover on mobile | — |
| AttributeTable (12.4) | — | DSR-02 |
| ProductGallery (12.4) | — | DSR-03 |
| PriceDisplay, `formatMXN` (12.6) | DS:formatting.md | — |
| AddressForm, invoice section (13.2) | form field, input, select; `UForm` with Zod (CR-28) | — |
| CartLine (13.2) | card, input, button | — |
| Header, footer, logo | site header, site footer, `CnLogo` | — |
| `error.vue`, empty cart, loading (12.10, 13.7) | DS error-page, empty-state and loading patterns | — |
| "Próximamente" page (G32) | `CnLogo`, a DS motif, `CnMediaCard` | — |
| OrderTimeline (14.2) | — | DSR-08 `[R2]` |

**Formatting.** `app/utils/money.ts` holds the locale `es-MX` and the currency code in one place; `formatMXN` returns the `Intl.NumberFormat` output with no suffix (CR-30, ADR-0024). Dates use `Intl.DateTimeFormat` with the store timezone passed explicitly (CR-31, G5); `dateStyle: 'long'` in sentences and `'medium'` in cards and lists (DS:formatting.md).

**Email.** Phase 11 builds every template from the DS email package (DS:email-components.md, DS:email-layouts.md):

- The compiled HTML of the pinned version is vendored into `api/apps/notifications/templates/email/ds/`, with `ds-email-manifest.json` recording the DS version and each file's sha256 (P11-V12). The API image needs no Node toolchain.
- Each `{{ slot_name }}` placeholder becomes a Django template variable. Django escapes variables by default; a slot that needs markup, such as order lines, waits for DSR-04 and is never marked safe by hand.
- Every template follows the six-part reference layout, fills every slot, and has a plain-text counterpart built from the same values (P11-V13).
- The header's `{{ logo_url }}` is a raster logo the store hosts (DSR-05).
- R1 templates: `order_confirmation`, `oxxo_voucher`, `order_expired`, `order_shipped`, `order_cancelled`, `refund_issued`, `cfdi_issued`. R2 templates: `verify_email`, `password_reset`, `ready_for_pickup`, `pickup_reminder`, `preorder_arrived`.

### 4.6 Testing strategy

The rules are CR-37 to CR-44. The reports are in §0.2 and the commands in §0.3.

#### Test layers

| Layer | Tool | Location | Marker / project | In `make test` | In `make test-all` |
|---|---|---|---|---|---|
| Unit | pytest, pytest-django, factory_boy | `api/tests/unit/<app>/` | — | ✅ | ✅ |
| Property-based | hypothesis | `api/tests/property/` | — | ✅ `dev` profile | ✅ `ci` profile |
| Integration | pytest-django against Postgres in docker | `api/tests/integration/<app>/` | — | ✅ | ✅ |
| Concurrency | pytest-django, threads with separate DB connections | `api/tests/concurrency/` | `concurrency` | ✅ | ✅ |
| API | DRF `APIClient` | `api/tests/api/<app>/` | — | ✅ | ✅ |
| Contract — providers | pytest, drivers from 9.13 and 10.13 | `api/tests/contract/{payments,carrier}/` | `sandbox` only in Phase 16 | ✅ mock | ✅ mock |
| Vendor adapters | pytest with fake SDK clients | `api/tests/unit/<app>/` | `integrations` | — | — (CI job `test-integrations`, from Phase 16) |
| Contract — OpenAPI | drf-spectacular snapshot + schemathesis | `api/tests/contract/openapi/` | `slow` for full fuzz | ✅ snapshot + 25 examples | ✅ 200 examples |
| Migration | django-test-migrations | `api/tests/migrations/` | `slow` for the full round trip | ✅ per-migration tests | ✅ + full round trip |
| Architecture | pytest + `ast`; Vitest scans for `web/` | `api/tests/architecture/`, `web/tests/architecture/` | — | ✅ | ✅ |
| Frontend unit / component | Vitest + @nuxt/test-utils | `web/tests/{unit,components}/` | — | ✅ | ✅ |
| E2E | Playwright against `docker compose`, mocks on | `web/e2e/` | projects `desktop`, `mobile` | Only the task's specs, through `make e2e` | ✅ |
| SSR (raw HTML) | Playwright `request` fixture, no JavaScript executed | `web/e2e/*_ssr.spec.ts` | same | Same as E2E | ✅ |
| Performance / SEO | Lighthouse CI (`@lhci/cli`) | `web/lighthouserc.json`, `web/tests/perf/` | — | — | ✅ |
| Accessibility | `@axe-core/playwright` inside E2E specs | `web/e2e/` | same | Same as E2E | ✅ |
| Offline clean clone | CI job + `docker-compose.offline.yml` | `.github/workflows/ci.yml` | job `clean-clone-offline` | — | CI only (15.5) |
| Static checks | ruff, mypy, eslint, vue-tsc | — | — | ✅ | ✅ |
| Spec checks | `check_register` in `make test`; `check_traceability` in `make test-all` | `scripts/` | — | ✅ register | ✅ both |

#### Layer details

**Unit.**

- pytest-django with `DJANGO_SETTINGS_MODULE=config.settings.test`, `--reuse-db`, `--strict-markers`.
- One factory module per app in `api/tests/factories/`, with traits for common states: `OrderFactory(paid=True)`, `VariantFactory(apparel=True)`, `StockItemFactory(on_hand=5)`. Tests build state through factories and services, never raw `objects.create` on `order` or `stock_item` (CR-42).
- Time-dependent logic uses `time-machine`. No `sleep()` in any test (CR-43).
- `pytest-randomly` shuffles test order and prints its seed; `--randomly-seed=<seed>` reproduces an order-dependent failure.
- `pytest-xdist` (`-n auto`) parallelises. `pytest-timeout` (`timeout = 60`) turns a deadlocked concurrency test into a failure.

**Property-based.** Hypothesis profiles `dev` (`max_examples=100`) and `ci` (`max_examples=1000`, `derandomize=True`, `deadline=None`) are registered in `api/tests/conftest.py` and selected by `HYPOTHESIS_PROFILE`. The example database lives in `.hypothesis/`, which CI caches. Required properties:

- **Totals and IVA, `compute_totals` (7.9):** results are always `int`; `total == subtotal + shipping - discount`; `tax_included_cents == round(total * 16 / 116)`; nothing is negative; in R2, pickup implies `shipping == 0`.
- **Money conversion (9.2):** `pesos_to_cents(cents_to_pesos(x)) == x` for every non-negative `x`, and sub-centavo input raises.
- **Inventory:** a `RuleBasedStateMachine` over `receive_stock`, `reserve`, `commit_reservations`, `release_reservations` and `adjust_stock` (and `record_in_store_sale` in R2). After every step: `0 <= reserved <= on_hand`; the sum of ledger deltas equals `on_hand`; `reserved` equals the sum of `held` stock reservations; and in R2, `preorder_committed <= preorder_limit`.
- **State machine (8.A):** a `RuleBasedStateMachine` firing random events at an order. Illegal events raise `IllegalTransition` and leave the row unchanged; terminal states accept no event; every legal transition writes exactly one `order_event`.
- DB-backed stateful tests subclass `hypothesis.extra.django.TestCase`, which rolls back after every example.

**Integration.**

- `config.settings.test` points at the `db` service: the same `postgres:16` image as local development.
- A session-scoped autouse fixture asserts `connection.vendor == "postgresql"` and aborts the run otherwise (CR-40).
- Tests that depend on commit semantics (`transaction.on_commit`, row locks) use `@pytest.mark.django_db(transaction=True)`.

**Concurrency.** `api/tests/concurrency.py::run_concurrently(fn, n)` starts `n` threads behind a `threading.Barrier`, each with its own DB connection, closed on exit. Tests are marked `concurrency` and use `django_db(transaction=True)`. Required cases: reserving the last unit (Phase 4); `payment_approved` racing `deadline_passed` (Phase 8); duplicate webhook delivery (PAY-09); in R2, a counter sale racing a checkout (Phase 4).

**API.** `api_client` and `auth_client(customer)` wrap DRF `APIClient` with `enforce_csrf_checks=True`, so CSRF enforcement is under test. Every endpoint gets tests for the success path, validation errors (field-level error shape), permission (another customer's resource returns 404), and rate limits.

**Contract — OpenAPI.**

- `api/openapi.snapshot.yml` is committed. A test regenerates the schema with `manage.py spectacular --validate --fail-on-warn` and fails on any difference. An intentional change uses `make schema-update`, which rewrites the snapshot and regenerates `web/app/types/api.d.ts`; both files change in one commit.
- Schemathesis runs in-process against the Django WSGI application, with the checks `not_a_server_error`, `status_code_conformance`, `content_type_conformance` and `response_schema_conformance`, anonymously and as staff. It excludes `/api/webhooks/*` (covered by 9.13) and `/dev/*`.

**Migration.** django-test-migrations' `migrator` fixture tests every data migration forward and backward. `test_all_migrations_reversible` (`slow`) migrates an empty database to the latest state, back to zero and forward again. `makemigrations --check --dry-run` fails the run if a model change lacks a migration.

**Architecture.** The §4.3 enforcement tests, plus:

- `test_no_direct_state_assignment.py`: an `ast` scan of `api/apps` that fails on any assignment to `.state`, any `setattr(…, "state", …)` and any `.update(state=…)`, except in `apps/orders/state_machine.py`.
- `test_stock_mutation_boundary.py`: the same technique for `on_hand` and `reserved`, allowed only in `apps/inventory/services.py`.
- The storefront styling scan (P12-V26) and the DS pin check (P12-V27).

**Frontend unit and component.** `web/vitest.config.ts` uses `defineVitestConfig` with `environment: "nuxt"`. Components are mounted with `mountSuspended`, and API calls are stubbed with `registerEndpoint`, never by mocking `$fetch` globally. Fixture payloads are typed against `app/types/api.d.ts`, so a fixture that drifts from the API fails `vue-tsc --noEmit`. Coverage comes from `@vitest/coverage-v8`.

**E2E.**

- `web/playwright.config.ts` starts the stack through `webServer` with `docker compose -f docker-compose.yml -f docker-compose.e2e.yml up --wait`. From Phase 15, `make test-all` runs Playwright inside the `e2e` compose service instead, so the same run works offline (15.5). The override pins every provider to its mock, sets `MOCK_WEBHOOK_DELAY_SECONDS=0`, and runs `manage.py seed_e2e`.
- Specs that change stock use variants seeded for that spec alone (SKU prefix `E2E-<spec>`) and run serially inside their file. Everything else runs in parallel.
- Projects: `desktop` (Desktop Chrome) and `mobile` (Pixel 7 viewport).
- `trace: "retain-on-failure"`. Retries: 0 locally, 1 in CI with `failOnFlakyTests: true`, so a test that passes only on retry still fails the run.
- Locators follow §0.5 rule 4: role, label, text, then test ID. No spec waits for `networkidle`.
- Offline guard: a shared fixture in `web/e2e/fixtures.ts` lets `localhost` requests through and aborts anything else, failing the test that made it.

**Accessibility.** Every page-level spec ends with `expectNoA11yViolations(page)`, which runs axe with the tags `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa` and `wcag22aa`, and allows no `serious` or `critical` violation (CR-35, P1-V20). An exception needs an entry in `web/e2e/a11y-exceptions.ts` naming the rule, the selector, the reason and a spec ID. The file is empty at launch.

**Test settings (`config/settings/test.py`).** Every provider is set to its mock (`INVOICE_PROVIDER=manual`), and `DEV_TOOLS_ENABLED = True`. `EMAIL_FILE_DIR` and `MOCK_STORE_DIR` point at a per-test `tmp_path`. `PASSWORD_HASHERS` is MD5 for speed, and a dedicated test asserts that `prod.py` lists `Argon2PasswordHasher` first. `pytest-socket` is configured as in §4.3. `TEMPLATES[0]["OPTIONS"]["string_if_invalid"] = "⟦MISSING:%s⟧"`, so a missing template variable shows in the output.

#### Coverage gates

Branch coverage through `pytest-cov` (`branch = true`), omitting `*/migrations/*`, `config/settings/*`, `manage.py` and `api/tests/*`. The gates are checked at phase close (§0.2).

| Scope | Paths | Gate |
|---|---|---|
| Critical backend | `apps/inventory/*`, `apps/orders/*` (with `pricing.py`), `apps/payments/*` (with `money.py`) | ≥ 95 % branch |
| Overall backend | `api/apps/*` | ≥ 85 % branch |
| Frontend composables | `web/app/composables/**` | ≥ 80 % lines, branches, functions and statements |

coverage.py supports only a global `fail_under`, so the critical gate is a second step: `coverage report --include=<critical paths> --fail-under=95`.

Coverage never decreases (CR-44). `coverage-baseline.json` records each scope's percentage to two decimals. `scripts/coverage_ratchet.py` fails if any scope is lower than the baseline. When coverage rises, `make coverage-ratchet` rewrites the baseline in the same commit.

#### Traceability and the register

- Every Verify item carries an ID, `P<phase>-V<NN>`. Each maps to at least one automated test whose name contains the ID in lowercase with underscores: `test_p4_v01_concurrent_reserve_last_unit` in pytest, `p13_v02 double-click Pagar creates one order` in a Playwright title. Contract scenarios keep their own IDs (`test_pay_09_…`, `test_car_04_…`).
- Items that cannot be automated carry `[manual]` and appear in the phase-close report instead.
- `scripts/check_traceability.py --release R1` extracts every ID from the first column of the Verify tables in `SPEC.md` §6, collects test names with `pytest --collect-only -q`, `npx vitest list` and `npx playwright test --list`, plus the job names in `.github/workflows/*.yml`, and fails if an in-scope ID has no matching test. An ID tagged `[R2]` is out of scope while R1 is in progress. It runs in `make test-all` and generates Appendix A.
- `scripts/check_register.py` checks that every S, D, G, C and DSR ID cited in a test name, an `xfail` reason or a code comment exists in §2.4, and that no Resolved or Decided item still has an `xfail`. It runs in `make test` (P1-V22).

### 4.7 Environment variables

`DJANGO_SETTINGS_MODULE` selects the settings file: `config.settings.dev` locally, `config.settings.test` in the test suite, `config.settings.prod` in production. `dev.py` and `test.py` default every provider switch to its mock; `prod.py` rejects mock values and forces dev tools off (CR-20).

#### Core

| Variable | Where | Part A | Part B | Notes |
|---|---|---|---|---|
| `DJANGO_SETTINGS_MODULE` | api | `config.settings.dev` / `.test` | `config.settings.prod` | |
| `SECRET_KEY` | api | Any dev value | 50+ random characters | |
| `DATABASE_URL` | api | The compose `db` service | `postgres://…` from Lightsail | SQLite aborts the test suite (CR-40) |
| `ALLOWED_HOSTS` | api | `localhost` | Apex and www | |
| `CSRF_TRUSTED_ORIGINS` | api | `http://localhost:8080` | The public origin | |
| `SITE_URL` | api | `http://localhost:8080` | The public URL | Used in emails, `back_urls` and mock URLs |
| `SITE_ADDRESS` | proxy | `:8080` | The domain | Caddy site block |
| `NUXT_PUBLIC_API_BASE` | web | `/api` | `/api` | See G18 for the SSR path |
| `OWNER_ALERT_EMAIL` | api | `owner@cupnoobles.test` | The owner's monitored inbox; no default, so `prod.py` fails to start without it | Recipient of `low_stock_report` and `daily_digest` (G38) |
| `EMAIL_REPLY_TO` | api | `tienda@cupnoobles.test` | The monitored inbox on the domain (S3) | The `Reply-To` of every email (11.4) |

#### Provider switches (§4.3)

| Variable | Where | Part A | Part B | Values |
|---|---|---|---|---|
| `PAYMENT_PROVIDER` | api | `mock` | `mercadopago` | `mock` \| `mercadopago` |
| `CARRIER_PROVIDER` | api | `mock` | `manual` | `mock` \| `manual` |
| `EMAIL_PROVIDER` | api | `file` | `resend` or `ses` | `file` \| `resend` \| `ses` |
| `MEDIA_STORAGE` | api | `local` | `s3` | `local` \| `s3` |
| `POSTAL_CODE_DATASET` | api (loader only) | `sample` | `sepomex` | `sample` \| `sepomex` |
| `ERROR_TRACKING` | api | `off` | `sentry` | `off` \| `sentry` |
| `NUXT_PUBLIC_ERROR_TRACKING` | web | `off` | `sentry` | `off` \| `sentry` |
| `INVOICE_PROVIDER` | api | `manual` | `manual` | `manual` |

#### Mock and dev-tool settings (Part A only; ignored or refused in production)

| Variable | Where | Default | Notes |
|---|---|---|---|
| `DEV_TOOLS_ENABLED` | api | `true` in dev and test | Gates the simulator (9.10), the tracking page (10.10), the `/dev/test/` endpoints (13.8, 15.3) and dev commands. `prod.py` forces `false`. |
| `MOCK_STORE_DIR` | api | `var/mocks/` | Payment and carrier mock state (9.9, 10.9) |
| `MOCK_PAYMENT_WEBHOOK_SECRET` | api | Any dev value | Signs mock notifications |
| `MOCK_WEBHOOK_DELAY_SECONDS` | api | `2` (`0` under `docker-compose.e2e.yml`) | Delay before `mock-webhooks` delivers (9.11) |
| `EMAIL_FILE_DIR` | api | `var/emails/` | `FileEmailSender` output |
| `EMAIL_MOCK_FAIL` | api | unset | `1` forces send failures, for retry tests |
| `HYPOTHESIS_PROFILE` | test | `dev` | `ci` in `make test-all` |

#### Build and CI

| Variable | Where | Needed from | Notes |
|---|---|---|---|
| `NODE_AUTH_TOKEN` | web install, image build, CI | Phase 1 | S8. Reads the DS packages from GitHub Packages. Never in an image layer or in Git (§4.5). |

#### Real-provider credentials (Part B only)

| Variable | Where | Needed from | Notes |
|---|---|---|---|
| `MP_ACCESS_TOKEN`, `MP_PUBLIC_KEY` | api | Phase 16 | S2. Test credentials first; production at launch. |
| `MP_WEBHOOK_SECRET` | api | Phase 16 | Signature verification (16.4) |
| `EMAIL_PROVIDER_KEY` | api | Phase 17 | S4 |
| `DEFAULT_FROM_EMAIL` | api | Phase 17 | The `noreply@` sender (11.4) |
| `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | api | Phase 18 | Object storage |
| `CDN_BASE_URL` | api, web | Phase 18 | Image URLs |
| `MANUAL_CARRIER_NAME` | api | Phase 19 | S7 |
| `MANUAL_CARRIER_TRACKING_URL_TEMPLATE` | api | Phase 19 | Must contain `{tracking}` |
| `SENTRY_DSN` | api, web | Phase 21 | |

#### Business and pipeline settings

| Variable | Where | Part A (dev default, §2.5) | Part B | Notes |
|---|---|---|---|---|
| `RESERVATION_TTL_CARD_MINUTES` | api | `30` | `30` | See ADR-0046 |
| `RESERVATION_TTL_SPEI_HOURS` | api | `4` | D6 | |
| `RESERVATION_TTL_OXXO_HOURS` | api | `72` | D6 | |
| `PAYMENT_INSTALLMENT_OPTIONS` | api | `3,6` | D7 | |
| `WEBHOOK_MAX_AGE_SECONDS` | api | `300` | `300` | Signature timestamp tolerance, applied on both sides of now (9.A, G8, ADR-0044) |
| `WEBHOOK_INLINE_BUDGET_MS` | api | `2000` | `2000` | Inline processing budget before `process_webhooks` takes over (9.A, OA-54, ADR-0045) |
| `PICKUP_HOLD_DAYS` | api | `7` | D4 | `[R2]`, with pickup |
| `PURCHASE_LIMIT_WINDOW_DAYS` | api | No default; tests set it (D15) | D15 | Days the purchase-limit guard looks back (G31, ADR-0030). Required while any variant carries a limit. |

The pre-launch switch (G32, ADR-0038) is not an environment variable: it is the `prelaunch_mode` column of the `site_setting` table, edited in the admin. The store timezone (G5, ADR-0030) is the constant `America/Mexico_City`, not a setting.

### 4.8 Scheduled jobs

All jobs are Django management commands. Every one must be idempotent and safe to run concurrently with itself (REQ-022); `send_outbox` doesn't meet that until G17 is resolved.

- **Part A.** A `scheduler` service in `docker-compose.yml`, built from the `api` image, runs `supercronic infra/crontab`. The crontab is the single source for the table below. `docker-compose.e2e.yml` disables the scheduler, so E2E journeys drive time-dependent jobs through the command runner (15.3). The test suite calls the commands directly and never relies on the scheduler. `mock-webhooks` (9.11) is a separate dev service, not a job.
- **Part B.** The same `infra/crontab`. The production topology has no scheduler yet (G23).

| Command | Frequency | Purpose | Release |
|---|---|---|---|
| `expire_reservations` | every 5 min | Release lapsed holds; expire orders (T5) | R1 |
| `advance_orders` | every 5 min | Auto-completion (T12); in R2 also T14 and the pickup deadline (T15) | R1 |
| `reconcile_payments` | every 10 min | Catch dropped webhooks (9.7) | R1 |
| `process_webhooks` | every 1 min | Drain unprocessed `webhook_event` rows | R1 |
| `send_outbox` | every 1 min | Send queued email (11.1) | R1 |
| `sync_shipments` | every 30 min | Carrier status → T11 (10.11) | R1 |
| `low_stock_report` | daily | Variants at or below safety stock | R1 |
| `check_stock_integrity` | daily | Ledger and reservation invariants (G24) | R1 |
| `daily_digest` | daily | The owner's daily summary (21.4), including CFDI requests waiting and invoiced refunds to review | R1 |
| `purge_stale_carts` | weekly | Delete unconverted carts untouched for 60 days | R1 |
| `pg_backup` | weekly | Part B only (21.5) | R1 |
| `refresh_preorder_flags` | daily | Flip `is_preorder` after release (10.4) | R2 |

## 5. Implementation phases

Phases run in order. A phase starts only after the previous phase's phase-close report is complete (§0.2): every in-scope Verify ID passes in `make test-all`. "In-scope" means the release in progress (§1.2); a phase whose R1 scope is small still closes with its own report.

Three kinds of work run in parallel with any phase, because they happen outside this repository:

- **Owner actions.** Signups (S1–S8) and the decisions in §7.2. S2 (Mercado Pago verification) and S4 (email sending domain) involve waiting on third parties, so they start during Part A.
- **Design System requests.** DSR items are built and released in the DS repository, under its own spec. Each must be released before the phase that needs it.
- **Business preparation from the owner's guide.** Catalog data, policy texts and the opening stock count (GE tasks) feed D2, D5, D12 and D15.

| Phase | Name | Part | Release 1 scope | Done when | Needs first |
|---|---|---|---|---|---|
| 1 | Repository, tooling, local environment | A | All | One command starts the stack; every gate in §0.3 is wired; `make test-all` is green locally and in CI | S5, S8 |
| 2 | Database schema | A | All; R2 tables are created but unused | Migrations produce exactly `spec/schema.sql` (P2-V01) | The R1 schema items in §4.4 |
| 3 | Catalog domain and admin | A | All | Products of every launch type can be added in the admin, with images; the importer works | D14 stand-in |
| 4 | Inventory: stock, reservations, ledger | A | Without counter sales (4.5); adds receiving (G20) and bin locations (G34) | No oversell under concurrency (P4-V01); the ledger is complete | — |
| 5 | Public catalog API | A | All, plus pre-launch mode on the API (G32) | Read-only API with OpenAPI types; bounded queries | — |
| 6 | Customer accounts | A | Postal-code lookup (6.6) and guest order lookup (6.7) only | Both endpoints pass their Verify items | — |
| 7 | Cart and shipping quotes | A | Delivery only; no merge on login | A server-side cart with live prices and shipping quotes | D5 stand-in |
| 8 | Orders and the state machine | A | Delivery transitions; invoice data at checkout; purchase limits (G31); cost snapshot (G33) | Every R1 transition in 8.A is implemented, logged and tested | — |
| 9 | Payments (mocked) | A | All, plus the CFDI review flag on refunds | The payment contract suite passes against the mock (P9-V01) | D6, D7 stand-ins |
| 10 | Fulfillment (mocked) | A | Delivery, the CFDI admin queue and global-invoice export, and reporting exports. Pickup, pre-orders and counter sales are R2. | Delivery works end to end from the admin; the carrier contract suite passes (P10-V01) | — |
| 11 | Transactional email | A | The seven R1 templates, built from the DS email package | Every R1 trigger sends exactly one email | DSR-04, DSR-05 |
| 12 | Frontend foundation and catalog pages | A | All, plus the "próximamente" page (G32) | The catalog is server-rendered, built from the DS, and passes axe at 360 px | DSR-01, DSR-02, DSR-03, DSR-06, DSR-07; DSR-09 or the P12-V26 fallback |
| 13 | Frontend cart and checkout | A | Delivery only; "Quiero factura"; the purchase-limit message | A guest can buy through the simulator on both projects | — |
| 14 | Frontend account pages | A | `/rastrear` only (14.6) | Guest lookup passes P14-V09 | — |
| 15 | Local acceptance | A | Journeys J1, J3, J4, J8, J10 and J11; the demo; the offline proof | P15-V14 passes: `make test-all` from a clean clone with no network | — |
| 16 | Mercado Pago integration | B | All | The payment contract suite passes against the sandbox | S2; D6, D7, D13 |
| 17 | Email provider and DNS | B | All | Email arrives from an authenticated domain | S3, S4 |
| 18 | Object storage and CDN | B | All | Product images are served from the CDN | S1 |
| 19 | Carrier integration | B | All | The carrier contract suite passes with the manual carrier | S7 |
| 20 | Deployment, CI/CD and cost | B | All, plus the scheduler (G23) | A push to `main` reaches production with no manual step | D1 |
| 21 | Observability, backups and the runbook | B | All | Problems alert the owner; a restore has been practised | S6 |
| 22 | Launch (Release 1) | B | The launch checklist | Every checklist item is ticked; `check_placeholders` exits 0 | D2, D4, D5, D12, D15, D16, D18 |

**Milestones.** Local acceptance: P15-V14 passes; Part B starts only after it. Release 1: the Phase 22 checklist is complete and the store is open.

## 6. Task list

Each phase keeps the plan's structure: its deliverable, its normative subsections (8.A, 9.A, 10.A and so on), its tasks, its Verify table and the fixtures it introduces. Tasks are listed in execution order. A task's ID comes from the plan and never changes (§0.4), so a new task's number doesn't reflect its position.

Each task carries these fields:

- **Release · Gate** — `R1` or `R2`. `task` means the task report; `phase-close` means the task report plus the phase-close report (§0.2). An R2 task shows `Gate: —` and is skipped while Release 1 is in progress.
- **REQs** — the §3 requirements the task serves. A task that owns an acceptance ID of a requirement always lists that requirement.
- **Verifies** — the Verify IDs the task makes pass. Each Verify ID is owned by exactly one task. `[no-test: …]` explains a task without a test of its own.
- **Depends on** — tasks that must be `[x]` first. `Phase N closed` means that phase's phase-close task is `[x]`. A DSR item must be released, and an S item done.
- **Context** — what to read besides §0 and §2.
- **Open items** — §2.4 items that affect the task, and how.
- **Done when** — extra conditions. Otherwise a task is done when every Verify ID it lists passes and its task report is complete.

Part A — Local (Phases 1–15). Everything runs on one machine under `docker compose`, with no outbound connection to a third-party service (A13). Backend phases come first (1–11), then the storefront (12–14), ending in local acceptance (15).

### Phase 1 — Repository, tooling, local environment

**Deliverable:** a monorepo that starts with one command, with every test layer, gate and spec check from §4.6 wired up, and `make test-all` green on the skeleton, locally and in CI.

**Release 1 scope:** all tasks.

#### Bootstrap (owner, before T1.1)

Work arrives through `/task`, so the spec and the skill must be in the repository before the first task. The owner does this by hand:

1. Create the public repository on GitHub (S5) and grant it read access to the three DS packages (S8).
2. Commit to `main` the bootstrap pack: `SPEC.md`, `spec/schema.sql`, `CLAUDE.md`, `AGENTS.md`, `.claude/skills/`, `.agents/skills/`, `docs/review/web-interface-guidelines.md`, `.github/pull_request_template.md` and `.markdownlint-cli2.jsonc`.
3. Put a GitHub token with `read:packages` in the user-level `~/.npmrc` (§4.5).

#### Tasks

- [x] **T1.1 — Repository structure** (2026-10-19, bdf10df)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: [no-test: directories and placeholders only; T1.12a to T1.14b add the tests]
  - Depends on: bootstrap
  - Context: §4.1, §4.6

Create the repo structure:

```text
cupnoobles/
├── SPEC.md                   # this spec (bootstrap)
├── spec/schema.sql           # canonical schema (§4.4, bootstrap)
├── CLAUDE.md  AGENTS.md      # agent instructions (bootstrap)
├── .claude/skills/  .agents/skills/
├── api/                      # Django project
│   ├── config/               # settings, urls, wsgi, asgi
│   ├── apps/
│   │   ├── core/             # providers registry, media + error-tracking interfaces (§4.3)
│   │   ├── catalog/
│   │   ├── inventory/
│   │   ├── accounts/
│   │   ├── carts/
│   │   ├── orders/
│   │   ├── payments/
│   │   ├── shipping/         # includes carriers/ and postal.py (§4.3)
│   │   ├── invoicing/        # CFDI requests and InvoiceProvider (§4.3, §4.4)
│   │   └── notifications/    # email outbox, email/ adapters, templates/email/ds/ (§4.5)
│   ├── fixtures/             # mx_postal_codes_sample.csv, cfdi_catalogs.json (§4.3, §4.4)
│   ├── tests/                # layout per §4.6
│   │   ├── conftest.py       # Postgres guard, hypothesis profiles, tmp mock stores, use_provider
│   │   ├── factories/
│   │   ├── concurrency.py    # run_concurrently helper
│   │   ├── unit/  property/  integration/  concurrency/  api/
│   │   ├── contract/{payments,carrier,openapi}/
│   │   ├── migrations/
│   │   └── architecture/     # §4.3 enforcement + state-assignment + stock-mutation tests
│   ├── openapi.snapshot.yml  # committed schema snapshot (§4.6)
│   ├── pyproject.toml
│   └── Dockerfile
├── web/                      # Nuxt 4, extends the DS layer (§4.5)
│   ├── app/
│   ├── tests/{unit,components,architecture}/
│   ├── e2e/                  # Playwright specs, fixtures.ts (offline guard), a11y-exceptions.ts
│   ├── .npmrc                # scope line only, no token (§4.5)
│   ├── pnpm-workspace.yaml   # allowBuilds (§4.5)
│   ├── nuxt.config.ts
│   ├── vitest.config.ts
│   ├── playwright.config.ts
│   └── Dockerfile
├── proxy/
│   └── Caddyfile
├── infra/
│   ├── crontab               # the scheduled jobs (§4.8)
│   └── lightsail/            # deployment spec JSON
├── docs/
│   ├── decisions/            # ADRs (T1.15)
│   └── review/               # pinned web-interface guidelines (§0.5, bootstrap)
├── var/                      # gitignored: local media, emails, and mock provider stores (var/mocks/)
├── docker-compose.yml        # local dev only
├── docker-compose.e2e.yml    # E2E override: mocks pinned, zero webhook delay, seed_e2e
├── Makefile                  # the §0.3 targets
├── coverage-baseline.json    # coverage ratchet (§4.6)
├── scripts/                  # coverage_ratchet.py, check_traceability.py, check_register.py
├── .github/
│   ├── workflows/
│   └── pull_request_template.md
└── README.md
```

- [x] **T1.2 — Backend dependencies** (2026-10-20, fa20577)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: [no-test: dependency manifest; exercised by every later backend test]
  - Depends on: T1.1
  - Context: §4.3 (CR-23)

`api/` — Python 3.12, dependencies managed with `uv`. Core set:

```text
django>=5.1,<6
djangorestframework
django-environ
psycopg[binary]
argon2-cffi
drf-spectacular
django-cors-headers        # local dev only; production is same-origin
django-axes                # login brute-force lockout
jsonschema                 # validates product.attributes
gunicorn
whitenoise
# integrations (optional group; production image only — CR-23)
mercadopago resend boto3 django-storages sentry-sdk
# dev
pytest pytest-django pytest-socket pytest-cov pytest-xdist pytest-randomly pytest-timeout
factory-boy hypothesis time-machine schemathesis django-test-migrations syrupy
ruff mypy django-stubs
```

- [x] **T1.3 — Settings, secrets and password hashing** (2026-10-20, bc2f8a7)
  - Release: R1 · Gate: task
  - REQs: REQ-040
  - Verifies: P1-V14, P1-V16, P1-V18
  - Depends on: T1.2
  - Context: §4.3 (Boundaries), §4.7

`config/settings/` split into `base.py`, `dev.py`, `test.py`, `prod.py` (`test.py` as specified in §4.6). All secrets from the environment via `django-environ` (CR-50). `prod.py` must set: `DEBUG=False`, `SECURE_HSTS_SECONDS`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SESSION_COOKIE_SAMESITE="Lax"`, `SECURE_PROXY_SSL_HEADER`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`. The provider switches from §4.3 are read in `base.py`. `dev.py` and the test settings default every one to its mock (`INVOICE_PROVIDER=manual`). `prod.py` rejects mock values at startup and forces `DEV_TOOLS_ENABLED` to false (CR-20). The mock values are `PAYMENT_PROVIDER=mock`, `CARRIER_PROVIDER=mock` and `EMAIL_PROVIDER=file`; `MEDIA_STORAGE=local`, `POSTAL_CODE_DATASET=sample` and `ERROR_TRACKING=off` stay accepted until their phases (ADR-0027).

Set `PASSWORD_HASHERS` with `Argon2PasswordHasher` first (absorbs plan 1.4).

- ~~**T1.4 — Argon2 password hasher**~~ Absorbed by T1.3.

- [x] **T1.5 — Storefront app on the Design System layer** (2026-10-20, b96c8fa)
  - Release: R1 · Gate: task
  - REQs: REQ-050
  - Verifies: [no-test: the app renders and passes axe in P1-V09 (T1.13b); the pin is checked by P12-V27 (T12.14)]
  - Depends on: T1.1, S8
  - Context: §4.5
  - Open items: ~~S8 (blocking)~~ resolved (ADR-0026)

`web/` — create a Nuxt 4 app with pnpm, pinned to the Nuxt version of the DS consumer fixture (4.5.2). Follow §4.5 to install from GitHub Packages: commit `web/.npmrc` with the scope line only, keep the token in the user-level `~/.npmrc`, and set `allowBuilds` in `web/pnpm-workspace.yaml`.

- Add the three DS packages at one exact version (`1.0.0`, A17): `@vinsmokemau/cup-noobles-nuxt`, `@vinsmokemau/cup-noobles-tokens`, `@vinsmokemau/cup-noobles-email`. Extend the layer in `nuxt.config.ts`: `extends: ['@vinsmokemau/cup-noobles-nuxt']`.
- Add `@nuxtjs/sitemap`, `@nuxt/image` and `zod`. Do not add `@nuxt/ui` or `tailwindcss`: the layer brings them (C-11).
- Dev dependencies: `openapi-typescript`, `vitest`, `@nuxt/test-utils`, `@vue/test-utils`, `happy-dom`, `@vitest/coverage-v8`, `@playwright/test`, `@axe-core/playwright`, `@lhci/cli`, `vue-tsc`.
- No `main.css` and no `ui.colors` override (CR-27).

- [x] **T1.6 — Local stack** (2026-10-20, da56925)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: [no-test: P1-V01 and P1-V02 (T1.13b) test the stack through the proxy]
  - Depends on: T1.3, T1.5
  - Context: §4.1, §4.8

`docker-compose.yml` for local development: `postgres:16`, `api`, `web`, `caddy`, and `scheduler` (built from the `api` image, running `supercronic infra/crontab`; §4.8). `infra/crontab` starts empty; each job's task adds its line. The local Caddyfile mirrors production routing exactly — `/api/*` and `/admin/*` to Django, `/*` to Nuxt — so routing bugs surface locally. The `web` image build receives `NODE_AUTH_TOKEN` as a build secret, never as a build argument or layer (§4.5).

- [x] **T1.7 — Proxy routing** (2026-10-21, db5ce9c)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: [no-test: P1-V01 and P1-V02 (T1.13b)]
  - Depends on: T1.6
  - Context: §4.1

`proxy/Caddyfile`:

```text
{$SITE_ADDRESS} {
    encode gzip zstd
    handle /api/* { reverse_proxy api:8000 }
    handle /admin/* { reverse_proxy api:8000 }
    handle /static/* { reverse_proxy api:8000 }
    handle /media/* { reverse_proxy api:8000 }   # local media (§4.3); unused in production
    handle /dev/* { reverse_proxy api:8000 }     # dev tools (9.10, 10.10); 404 in production
    handle { reverse_proxy web:3000 }
}
```

- [x] **T1.17 — Design System 1.0.1** (2026-10-20, e109ea2)
  - Release: R1 · Gate: task
  - REQs: REQ-050
  - Verifies: [no-test: `nuxt typecheck` passes; the pin is checked by P12-V27 (T12.14)]
  - Depends on: T1.5
  - Context: §4.5
  - Open items: DSR-10 resolved by this task

DS 1.0.0 fails `vue-tsc` in `CnMediaCard.vue` (DSR-10). Raise the three DS packages in `web/` to exactly `1.0.1`, which fixes it (A17). Refresh `pnpm-lock.yaml`. `nuxt typecheck` must pass. The vendored email HTML does not exist yet (Phase 11), so there is nothing to refresh.

- [x] **T1.8 — Linters and pre-commit** (2026-10-21, 9b6aeb2)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: [no-test: the static checks run in `make test`]
  - Depends on: T1.5, T1.17
  - Context: §0.3

`ruff` for lint and format (replaces black, isort and flake8). `eslint` and `prettier` through `@nuxt/eslint`. `markdownlint-cli2` on `SPEC.md`, `docs/` and `README.md`, with the bootstrap `.markdownlint-cli2.jsonc`, so every spec edit stays well-formed. A pre-commit hook running all three; `make test` runs them too.

- [x] **T1.11 — Integration scaffolding** (2026-10-21, db85f84)
  - Release: R1 · Gate: task
  - REQs: REQ-040
  - Verifies: P1-V12, P1-V15, P1-V19
  - Depends on: T1.3
  - Context: §4.3

Integration scaffolding from §4.3:

- `apps/core/providers.py` with the registry, including `INVOICE_IMPLS`, and the `use_provider` pytest fixture
- the Protocols in §4.3, including `Attachment` on `OutgoingEmail` and `InvoiceProvider` (implementations arrive in their phases)
- `tests/architecture/test_vendor_imports.py` and `test_provider_selection.py`
- `pytest-socket` configured with `--disable-socket --allow-hosts=127.0.0.1,localhost,db`
- the ESLint `no-restricted-imports` rule for `@sentry/*`

- [x] **T1.15 — Seed the decision records** (2026-10-21, 6d80c8a)
  - Release: R1 · Gate: task
  - REQs: REQ-070
  - Verifies: [no-test: documents; `check_register` (P1-V22, T1.14b) checks that every resolved item cites an existing ADR]
  - Depends on: T1.1
  - Context: §2, §4.2
  - Done when: `docs/decisions/` holds the template and ADR-0001 to ADR-0025, each `accepted`, and `docs/decisions/README.md` lists them.

Write `docs/decisions/0000-adr-template.md` (context, decision, consequences, status, source) and one ADR per row of §4.2. Each ADR's context carries the plan's reasoning for that decision; dated prices stay in Appendix C. ADR-0001 records A1–A19 with their cost to change; ADR-0002 records that dev defaults are placeholders, never business values. Every source is an owner answer (§2.6) or a plan section; nothing new is decided here.

- [x] **T1.12a — Backend test configuration** (2026-10-21, 8d6c0ba)
  - Release: R1 · Gate: task
  - REQs: REQ-042, REQ-072
  - Verifies: P1-V04, P1-V13
  - Depends on: T1.11
  - Context: §4.6 (Unit, Integration, Test settings)

- `pyproject.toml`: pytest options (`--strict-markers`, `--reuse-db`, `-p randomly`, `timeout = 60`), markers `slow`, `concurrency` and `sandbox`, and coverage settings (`branch = true`, omits per §4.6).
- `tests/conftest.py`: the Postgres-only guard; hypothesis profiles `dev` and `ci`; autouse `tmp_path` for `EMAIL_FILE_DIR` and `MOCK_STORE_DIR`; `api_client` and `auth_client` with CSRF enforced; `use_provider`; `clock`; `pytester`.

- [x] **T1.12b — Concurrency helper and code checkers** (2026-10-21, 3dc7693)
  - Release: R1 · Gate: task
  - REQs: REQ-011, REQ-020
  - Verifies: P1-V05
  - Depends on: T1.12a
  - Context: §4.6 (Concurrency, Architecture)

- `tests/concurrency.py::run_concurrently`, plus one self-test showing that two threads really hold separate connections.
- `tests/architecture/test_no_direct_state_assignment.py` and `test_stock_mutation_boundary.py`, with the checkers exposed as `check_source(path, source)` for self-tests.

- [x] **T1.12c — Contract and migration harness** (2026-10-21, 35ec3db)
  - Release: R1 · Gate: task
  - REQs: REQ-054
  - Verifies: P1-V07
  - Depends on: T1.12a
  - Context: §4.6 (Contract — OpenAPI, Migration)

- `tests/contract/openapi/`: the snapshot test and the schemathesis test.
- `tests/migrations/test_all_migrations_reversible.py`.

- [x] **T1.16 — Health endpoint** (2026-10-21, a8e301d)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P1-V11, P1-V17
  - Depends on: T1.12a
  - Context: §4.1

Per G1's resolution (ADR-0028): `GET /api/health/` runs `SELECT 1` and returns 200 with `{"db": "ok"}`. If the database is unreachable, it returns 503. Phase 20 (20.4) keeps only the Lightsail health-check configuration.

- [x] **T1.13a — Frontend unit test configuration** (2026-10-21, ca3bbff)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: [no-test: the configuration is exercised by the first unit test in Phase 12; `vue-tsc` and `eslint` already run in `make test`]
  - Depends on: T1.5
  - Context: §4.6 (Frontend unit and component)

`vitest.config.ts` with `environment: "nuxt"` and coverage thresholds for `app/composables/**`.

- [x] **T1.13b — End-to-end harness** (2026-10-21, 20ce6fe)
  - Release: R1 · Gate: task
  - REQs: REQ-042, REQ-051
  - Verifies: P1-V01, P1-V02, P1-V08, P1-V09, P1-V20
  - Depends on: T1.7, T1.13a
  - Context: §4.6 (E2E, Accessibility), §0.5 (rule 4)

- `playwright.config.ts`: `webServer` on the compose E2E stack, `desktop` and `mobile` projects, CI retries with `failOnFlakyTests`.
- `e2e/fixtures.ts`: the offline guard, and `expectNoA11yViolations(page)` wrapping `AxeBuilder` with the tags `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa` and `wcag22aa` (CR-35).
- `docker-compose.e2e.yml` and a first `manage.py seed_e2e`.
- One smoke spec: the app's index page loads and passes axe.

- [x] **T1.14a — Make targets and coverage ratchet** (2026-10-21, 19f104d)
  - Release: R1 · Gate: task
  - REQs: REQ-071, REQ-073
  - Verifies: P1-V03, P1-V06
  - Depends on: T1.12c, T1.13b
  - Context: §0.3, §4.6 (Coverage gates)

- The `Makefile` targets from §0.3, each printing a short summary on success and the failing step's full output on failure.
- `scripts/coverage_ratchet.py`, and an initial `coverage-baseline.json` captured from the first green run.

- [x] **T1.14b — Spec checks** (2026-10-21, af55035)
  - Release: R1 · Gate: task
  - REQs: REQ-070
  - Verifies: P1-V10, P1-V21, P1-V22
  - Depends on: T1.14a, T1.15
  - Context: §0.4, §2.4, §4.6 (Traceability and the register)

- `scripts/check_traceability.py --release <R>`: reads the Verify tables of `SPEC.md` §6 and enforces §4.6. `make test-all` runs it with the release in progress.
- `scripts/check_register.py`: the register check in §4.6. `make test` runs it.

- [x] **T1.10 — README** (2026-10-22, 6a64766)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: [no-test: documentation]
  - Depends on: T1.14b
  - Context: §0.3, §4.5, §4.7

`README.md` with: how to start, how to install the DS packages (§4.5), how to run migrations, how to seed, how to run tests, where secrets live. Keep it current — it is the only onboarding doc besides this spec.

- [x] **T1.9 — Continuous integration** (2026-10-23, 9be4861)
  - Release: R1 · Gate: phase-close
  - REQs: REQ-073
  - Verifies: P1-V23 [manual]
  - Depends on: T1.10
  - Context: §0.3, §4.5 (Install and access), §4.6
  - Done when: the first CI run on `main` is green, and the owner has configured branch protection.

`.github/workflows/ci.yml` runs `make test-all` on every push and pull request.

- `concurrency` cancels a run superseded by a newer push to the same branch.
- `permissions: contents: read, packages: read`; `actions/setup-node` with `registry-url: https://npm.pkg.github.com` and `scope: '@vinsmokemau'`; the install step receives `NODE_AUTH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` (§4.5).
- Caches `.hypothesis/`, the `uv` cache and the pnpm store; uploads the coverage HTML, the Playwright HTML report and traces as artifacts.

`.github/pull_request_template.md` comes with the bootstrap pack: the task ID, the task report and, for a phase-close task, the phase-close report (§0.2), and a spec-sync checklist. Keep it in line with §0.2 when the reports change.

The owner configures branch protection on `main`: the `test-all` check is required, force-pushes are disallowed, and merging is blocked while it is red. The agent lists the steps; it does not change GitHub settings (§0.1 step 12). The settings in force are recorded in ADR-0029.

#### Verify — test specification

> Every ID below is a named test (§4.6). The phase closes when every in-scope ID passes in `make test-all` (§0.2). ⚠️ G# marks a test written against a gap's proposed resolution, `xfail(strict=True, reason="G#")` until the gap is decided (§2.4). `[R2]` marks an ID outside Release 1; `[manual]` an ID checked by hand in the phase-close report.

Phase 1 also builds the frontend test harness, so several of its items are Playwright tests (layer E2E).

**From the original Verify items:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P1-V01 | E2E | `web/e2e/p1_stack.spec.ts` › `p1_v01 same origin serves web and api` | Through Caddy on `localhost:8080`: `/` returns Nuxt HTML and `/api/schema/` returns OpenAPI JSON, on the same host and port. |
| P1-V02 | E2E | `web/e2e/p1_stack.spec.ts` › `p1_v02 admin login reachable` | `/admin/login/` returns 200 with the Django login form through Caddy. |
| P1-V03 | architecture | `api/tests/architecture/test_suite_config.py::test_p1_v03_test_all_runs_every_layer` | The `test-all` recipe parsed from the `Makefile` contains every step listed for it in §0.3; deleting any one makes the test fail. *The CI half is P1-V23.* |
| P1-V04 | integration | `api/tests/integration/test_harness.py::test_p1_v04_sqlite_aborts_suite` | Via `pytester`, a run with `DATABASE_URL=sqlite://…` exits non-zero before any test executes, with the Postgres-guard message. |
| P1-V05 | architecture | `api/tests/architecture/test_checker_selftest.py::test_p1_v05_state_and_stock_violations_detected` | Checkers fed `order.state = "paid"` in `apps/catalog/x.py`, `setattr(o, "state", …)`, `.update(state=…)` and `stock_item.on_hand -= 1` outside `apps/inventory/services.py` report violations. The same snippets in allowlisted modules report none. |
| P1-V06 | unit | `scripts/tests/test_coverage_ratchet.py::test_p1_v06_ratchet_rejects_decrease` | Exit 1 when any scope is below the baseline, below its gate, or when the baseline file itself was lowered against `HEAD`. Exit 0 when equal or higher. |
| P1-V07 | contract | `api/tests/contract/openapi/test_snapshot.py::test_p1_v07_snapshot_detects_drift` | The comparator reports a diff for a schema with a renamed field. The real snapshot test passes on an unchanged tree. |
| P1-V08 | E2E | `web/e2e/p1_guard.spec.ts` › `p1_v08 offline guard aborts external request` | A page request to `https://example.com` is aborted and marks the test failed (asserted in a self-test project with `test.fail()`). |
| P1-V09 | E2E | `web/e2e/p1_smoke.spec.ts` › `p1_v09 index page loads and passes axe` | On both projects the app's index page loads and `expectNoA11yViolations` passes. |
| P1-V10 | unit | `scripts/tests/test_check_traceability.py::test_p1_v10_missing_id_fails` | A spec fixture containing an ID with no matching collected test → exit 1 naming that ID. `[manual]` items are ignored. All IDs present → exit 0. |
| P1-V11 | API | `api/tests/api/test_health.py::test_p1_v11_health_ok` | `GET /api/health/` → 200 with `{"db": "ok"}`. |
| P1-V12 | architecture | `api/tests/architecture/test_vendor_imports.py::test_p1_v12_vendor_imports_confined` | The real tree passes. A checker self-test flags `import mercadopago` placed in `apps/orders/`. |
| P1-V13 | integration | `api/tests/integration/test_harness.py::test_p1_v13_external_socket_blocked` | `socket.create_connection(("example.com", 443))` raises `SocketBlockedError`; a connection to `db` succeeds. |
| P1-V14 | unit | `api/tests/unit/core/test_providers.py::test_p1_v14_prod_rejects_mock[switch]` | For each provider switch with a mock value, a subprocess running `django.setup()` with `config.settings.prod` exits non-zero with `ImproperlyConfigured`. |

**Added negative and edge cases:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P1-V15 | unit | `api/tests/unit/core/test_providers.py::test_p1_v15_unknown_provider_value_rejected[switch]` | Any unknown value (e.g. `PAYMENT_PROVIDER=stripe`) raises `ImproperlyConfigured` listing the allowed values, for every registry switch. |
| P1-V16 | unit | `api/tests/unit/core/test_settings.py::test_p1_v16_prod_forces_dev_tools_off` | `prod.py` with `DEV_TOOLS_ENABLED=true` in the environment still yields `False`. |
| P1-V17 | API | `api/tests/api/test_health.py::test_p1_v17_health_503_when_db_down` | When the DB cursor raises `OperationalError`, `/api/health/` returns 503. |
| P1-V18 | unit | `api/tests/unit/core/test_settings.py::test_p1_v18_prod_hasher_is_argon2` | `prod.py` lists `Argon2PasswordHasher` first; `test.py` uses MD5 (§4.6). |
| P1-V19 | architecture | `api/tests/architecture/test_provider_selection.py::test_p1_v19_implementations_imported_only_by_registry` | A self-test snippet importing `apps.payments.mock` from `apps/orders/` is flagged; the real tree passes. |

**Added in conversion:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P1-V20 | E2E | `web/e2e/p1_guard.spec.ts` › `p1_v20 axe runs the wcag 2.2 aa tags` | `expectNoA11yViolations` runs axe with exactly the tags `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa` and `wcag22aa`. A fixture page with a target smaller than 24 × 24 px (WCAG SC 2.5.8) fails it. |
| P1-V21 | unit | `scripts/tests/test_check_traceability.py::test_p1_v21_release_aware` | `check_traceability` reads the Verify tables of `SPEC.md` §6. Run with `--release R1`: an R1 ID with no matching test exits 1 naming it; an ID tagged `[R2]` with no test passes; `[manual]` IDs are listed, not required. |
| P1-V22 | unit | `scripts/tests/test_check_register.py::test_p1_v22_register_consistency` | `check_register` exits 1 when a test name, `xfail` reason or code comment cites an S, D, G, C or DSR ID absent from §2.4, when an item marked Resolved or Decided still has an `xfail`, or when a resolved item cites an ADR file that doesn't exist. The real tree passes. |
| P1-V23 [manual] | CI | `.github/workflows/ci.yml` job `test-all` | `make test-all` is green on `main`; a pull request with a deliberately failing test turns the check red, and branch protection blocks merging it (ADR-0029). |

**Fixtures and factories introduced** (reused by later phases)

- `api_client`, `auth_client(customer)` — DRF `APIClient` with `enforce_csrf_checks=True` (`auth_client` serves staff in R1 and customers in R2)
- `use_provider(setting, value)` — `override_settings` plus registry `cache_clear()`
- `clock` — a `time-machine` traveller fixture used for every TTL, deadline and boundary test
- `run_concurrently(fn, n)` — the thread + `Barrier` helper with per-thread connections
- autouse `tmp_mock_stores` — points `MOCK_STORE_DIR`, `EMAIL_FILE_DIR` and `MEDIA_ROOT` at `tmp_path`
- `check_source(path, source)` — the AST checkers exposed for self-tests
- `pytester` (enabled via `pytest_plugins`)
- Playwright `web/e2e/fixtures.ts` — `page` with the offline guard, `expectNoA11yViolations(page)`

### Phase 2 — Database schema

**Deliverable:** the complete schema, created by Django migrations, matching `spec/schema.sql` exactly.

**Release 1 scope:** all tasks. Tables and columns used only in Release 2 are created now and stay unused (§4.4).

#### How to build it

Django models are the source of truth in code; `spec/schema.sql` is the specification they must produce (§4.4). P2-V01 parses that file and compares it with `pg_catalog` after `migrate`.

Anything Django's ORM cannot express — `CHECK` constraints beyond `CheckConstraint`, GIN indexes with `jsonb_path_ops`, generated `tsvector` columns, partial unique indexes — goes in a `migrations.RunSQL` operation with a matching `reverse_sql`. Do not skip these. **The `CHECK` constraints are the thing that stops an oversell at 2am when application logic has a bug.** Each of T2.1a, T2.1b and T2.1c writes the `RunSQL` operations for its own tables.

The Release 1 schema items in §4.4 (G3, G5, G28, G31, G33, G34) are best decided before T2.1a. An item decided after Phase 2 closes is an amendment to `spec/schema.sql` plus a new migration.

#### Tasks

- [x] **T2.1a — Customer model and catalog tables** (2026-10-23, 594fc38)
  - Release: R1 · Gate: task
  - REQs: REQ-013
  - Verifies: P2-V03, P2-V06, P2-V08, P2-V12
  - Depends on: Phase 1 closed
  - Context: §4.4; `spec/schema.sql` (CATALOG, and `customer` under CUSTOMERS); "How to build it" above

Set `AUTH_USER_MODEL = "accounts.Customer"` **before the first migration** (absorbs plan 2.3). Changing it later is extremely painful. `customer` is used in Release 1 for staff, who sign in to the admin with it.

Write the Django models and migrations for `customer` and the catalog tables: `product_type`, `category`, `franchise`, `brand`, `product`, `product_category`, `product_image` and `variant`, with their constraints and indexes, including the `RunSQL` operations above. `product` carries `is_featured` and `featured_position` (G28), and `variant` carries `purchase_limit` (G31); both come from ADR-0030. Verify with `python manage.py sqlmigrate <app> <migration>` and diff against `spec/schema.sql`.

- [x] **T2.1b — Inventory, geography, address, shipping and cart tables** (2026-10-23, ab0e487)
  - Release: R1 · Gate: task
  - REQs: REQ-010
  - Verifies: P2-V02, P2-V11
  - Depends on: T2.1a
  - Context: §4.4; `spec/schema.sql` (INVENTORY, CUSTOMERS, SHIPPING, CART); "How to build it" above

Write the models and migrations for `location`, `stock_item`, `stock_ledger`, `inventory_reservation`, `in_store_sale`, `in_store_sale_line`, `mx_state`, `mx_postal_code`, `address`, `shipping_zone`, `shipping_zone_state`, `shipping_rate`, `cart` and `cart_line`. `stock_item` carries `bin_location` (G34, ADR-0030). The foreign keys from `stock_ledger`, `inventory_reservation` and `cart` to `"order"` are added in T2.1c, after `"order"` exists. `in_store_sale`, `in_store_sale_line` and `address` are unused in Release 1 (§4.4).

- [x] **T2.1c — Order, payment, invoicing, fulfillment and outbox tables** (2026-10-23, f2e64ac)
  - Release: R1 · Gate: task
  - REQs: REQ-001, REQ-030, REQ-032, REQ-060, REQ-072
  - Verifies: P2-V01, P2-V04, P2-V07, P2-V09, P2-V10, P2-V13, P2-V16, P2-V17
  - Depends on: T2.1b
  - Context: §4.4; `spec/schema.sql` (ORDERS, PAYMENTS, INVOICING, FULFILLMENT, TRANSACTIONAL EMAIL OUTBOX); "How to build it" above

Write the models and migrations for `"order"`, `order_line`, `order_event`, `payment`, `webhook_event`, `invoice_request`, `invoice_document`, `shipment` and `email_outbox`, and add the deferred foreign keys from `inventory_reservation`, `stock_ledger` and `cart` to `"order"`. `"order"` carries `cart_token`, `idempotency_key` and `idempotency_fingerprint` with `order_idempotency_uq` (G3), and `order_line` carries `unit_cost_cents` (G33), both from ADR-0030. The per-year order-number sequences (G5) are created by the service on first use, not by a migration. After this task, `migrate` on an empty database produces exactly `spec/schema.sql` (P2-V01).

- ~~**T2.2 — Non-ORM schema objects**~~ Absorbed by T2.1a, T2.1b and T2.1c (each writes its own `RunSQL` with `reverse_sql`; the rule is in "How to build it").

- ~~**T2.3 — Custom user model**~~ Absorbed by T2.1a.

- [x] **T2.7 — Seed the states and the warehouse location** (2026-10-23, 4c2247b)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: [no-test: P2-V15 (T2.8) asserts the states seed; P2-V18 (T2.9) checks the placeholder location]
  - Depends on: T2.1c
  - Context: §2.5; §4.4
  - Open items: D4 (stand-in §2.5)

Seed `mx_state` with all 32 subdivisions (ISO 3166-2:MX codes). Seed one `location` row for the warehouse from D4 — in Part A through `manage.py seed_dev_defaults` (§2.5): code `almacen`, name `[PLACEHOLDER] Almacén Cup Noobles`, `kind = 'warehouse'`, `is_pickup_point = false`. It is never presented as a store (CR-47).

- [x] **T2.8 — Seed the launch product types** (2026-10-23, 35fe396)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P2-V15
  - Depends on: T2.7
  - Context: §2.5; §4.4 (the attribute-agnostic catalog)
  - Open items: D14 (stand-in §2.5)

Seed the launch `product_type` rows from the D14 stand-in: `tcg_sealed`, `board_game`, `apparel`, `figure` and `accessory`. Apparel gets `variant_axes = ["talla","color"]`; the others `[]`. Each `attribute_schema` carries `"$comment": "[PLACEHOLDER]"` until D14 is decided. The schemas use the example attributes in the `spec/schema.sql` comments; a type with no example (`board_game`, `accessory`) gets an empty schema. Running the seed twice changes nothing.

- [x] **T2.5 — Attribute validation** (2026-10-23, a319c66)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P2-V05, P2-V14
  - Depends on: T2.8
  - Context: §4.4 (the attribute-agnostic catalog)

Implement `apps/catalog/validation.py`: on `Product.save()` (and in the DRF serializer), validate `attributes` against `product_type.attribute_schema` using `jsonschema`. Raise `ValidationError` with the JSON-pointer path of the failure so the admin shows a usable message.

- ~~**T2.6 — Dynamic attributes widget**~~ Absorbed by T3.4.

- [x] **T2.9 — Placeholder check and the CFDI catalog sample** (2026-10-23, b1a4531)
  - Release: R1 · Gate: phase-close
  - REQs: REQ-065
  - Verifies: P2-V18
  - Depends on: T2.5
  - Context: §2.5; §4.4 (CFDI catalog codes); §4.7 (business settings)
  - Open items: D16 (stand-in §2.5)

Write `manage.py check_placeholders`. It exits non-zero while any §2.5 placeholder remains: a `location`, `shipping_zone` or `shipping_rate` name containing `[PLACEHOLDER]`; a product type whose `attribute_schema` carries `"$comment": "[PLACEHOLDER]"`; `api/fixtures/cfdi_catalogs.json` while it carries the same comment; a D6 or D7 setting still at its dev default. T15.8 adds `[DEMO]` rows to the list. The Phase 22 launch checklist requires it to exit 0.

Create `api/fixtures/cfdi_catalogs.json` with the two code lists offered at checkout, régimen fiscal and uso de CFDI: a small sample headed `SAMPLE — not authoritative`, with `"$comment": "[PLACEHOLDER]"`. The accountant confirms the real subset (D16).

#### Verify — test specification

> Every ID below is a named test (§4.6). The phase closes when every in-scope ID passes in `make test-all` (§0.2). ⚠️ G# marks a test written against a gap's proposed resolution, `xfail(strict=True, reason="G#")` until the gap is decided (§2.4). `[R2]` marks an ID outside Release 1; `[manual]` an ID checked by hand in the phase-close report.

**From the original Verify items:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P2-V01 | migration | `api/tests/migrations/test_schema_spec.py::test_p2_v01_schema_matches_canonical_ddl` | After `migrate` on an empty database, every table, column (type and nullability), named constraint and named index in `spec/schema.sql` exists in `pg_catalog`. There are no application tables beyond it. |
| P2-V02 | integration | `api/tests/integration/schema/test_constraints.py::test_p2_v02_reserved_le_on_hand` | A raw insert with `on_hand=0, reserved=1` raises `IntegrityError` naming `stock_reserved_le_on_hand`; `1, 1` is accepted. |
| P2-V03 | integration | `api/tests/integration/schema/test_constraints.py::test_p2_v03_duplicate_variant_options` | Identical `options` on one product are rejected by `variant_product_options_uq`, including the same keys in a different order. |
| P2-V04 | integration | `api/tests/integration/schema/test_constraints.py::test_p2_v04_order_total_arithmetic` | `total_cents ≠ subtotal + shipping − discount` is rejected; the exact sum is accepted. |
| P2-V05 | unit | `api/tests/unit/catalog/test_attribute_validation.py::test_p2_v05_error_names_json_pointer` | A `figure` with `{"numero": "abc"}` raises a validation error whose path is `/numero`, both from `Product.save()` and from the serializer. |
| P2-V06 | integration | `api/tests/integration/schema/test_indexes.py::test_p2_v06_attributes_gin_used` | With `SET LOCAL enable_seqscan = off`, `EXPLAIN` of `attributes @> '{"linea":"Nendoroid"}'` names `product_attributes_gin`. |

**Added negative and edge cases:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P2-V07 | migration | `api/tests/migrations/test_all_migrations_reversible.py::test_p2_v07_round_trip` | (`slow`) Empty → latest → zero → latest succeeds; every `RunSQL` reverses; `makemigrations --check` is clean. |
| P2-V08 | integration | `api/tests/integration/schema/test_constraints.py::test_p2_v08_preorder_constraints` | A pre-order without `expected_release_date` is rejected; `preorder_committed > preorder_limit` is rejected; `preorder_committed == preorder_limit` is accepted. |
| P2-V09 | integration | `api/tests/integration/schema/test_constraints.py::test_p2_v09_order_fulfillment_target` | Past `draft`: pickup without a location and delivery without an address are rejected; a `draft` with neither is accepted; a pickup order with `shipping_cents > 0` is rejected. |
| P2-V10 | integration | `api/tests/integration/schema/test_constraints.py::test_p2_v10_order_line_arithmetic` | `line_total ≠ unit × quantity` is rejected; `fulfilled_quantity > quantity` is rejected. |
| P2-V11 | integration | `api/tests/integration/schema/test_constraints.py::test_p2_v11_address_constraints` | A second active default address is rejected; a soft-deleted default does not block a new one; postal codes `0670` and `0670A` are rejected. |
| P2-V12 | integration | `api/tests/integration/schema/test_constraints.py::test_p2_v12_catalog_constraints` | `active` without `published_at` is rejected; a category that is its own parent is rejected; non-object `attributes` or `options` are rejected. |
| P2-V13 | integration | `api/tests/integration/schema/test_constraints.py::test_p2_v13_payment_constraints` | `refunded_cents > amount_cents` is rejected; the partial unique index allows many payments with `provider_payment_id IS NULL` but no duplicate non-null ids. |
| P2-V14 | unit | `api/tests/unit/catalog/test_attribute_validation.py::test_p2_v14_schema_rules[type]` | For each launch product type with a non-empty schema: an unknown key (`additionalProperties: false`), a missing required key, and a wrong JSON type are each rejected with a pointer path. |
| P2-V15 | integration | `api/tests/integration/schema/test_seeds.py::test_p2_v15_seed_states_and_types` | 32 `mx_state` rows with ISO 3166-2:MX codes; the 5 launch product types of the D14 stand-in; apparel axes `["talla","color"]`; running the seed twice changes nothing. |
| P2-V16 | integration | `api/tests/integration/schema/test_constraints.py::test_p2_v16_webhook_event_uniqueness` | A repeated `(provider, topic, external_id)` is rejected; two notifications with the same payment id and different notification ids are both accepted (9.A rule 4). |

**Added in conversion:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P2-V17 | integration | `api/tests/integration/schema/test_constraints.py::test_p2_v17_invoice_constraints` | A second `invoice_request` for one order is rejected; `issued` without `cfdi_uuid` or `issued_at` is rejected; a 4-digit fiscal postal code is rejected. `invoice_document` rejects a second document of the same kind for one request, and a file over 5 MB. |
| P2-V18 | integration | `api/tests/integration/schema/test_placeholders.py::test_p2_v18_check_placeholders_kinds` | `check_placeholders` exits non-zero for each placeholder kind in §2.5: a `[PLACEHOLDER]` location, zone or rate name; a product-type schema or the CFDI catalog file carrying the `[PLACEHOLDER]` comment; a D6 or D7 setting at its dev default. It exits 0 when none remain. |

**Fixtures and factories introduced** (reused by later phases)

- Factories: `ProductTypeFactory` (traits `tcg_sealed`, `board_game`, `apparel`, `figure`, `accessory`, using the launch schemas), `CategoryFactory`, `BrandFactory`, `FranchiseFactory`, `ProductFactory`, `VariantFactory`, `LocationFactory` (default: the warehouse; trait `pickup_point` for R2), `CustomerFactory`, `AddressFactory` (a valid Mexican address), `ShippingZoneFactory`, `ShippingRateFactory`, `InvoiceRequestFactory`
- `mx_states` (session-scoped) and `launch_product_types`
- `raw_sql(statement, params)` — executes SQL that bypasses the ORM, for constraint tests
- `canonical_ddl` — the statements parsed from `spec/schema.sql`

### Phase 3 — Catalog domain and admin

**Deliverable:** the owner can add a Nendoroid, a booster box, and a hoodie with three sizes through the admin, with images, and see them rendered correctly in a JSON API response.

**Release 1 scope:** all tasks.

#### Tasks

Execution order: T3.2, T3.1, T3.3, T3.4, T3.5, T3.6, T3.7. T3.2 comes first because `create_product` (T3.1) generates slugs with its rules. IDs keep their numbers (OA-30).

- [x] **T3.2 — Slugs** (2026-10-23, 10fbcc3)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P3-V05, P3-V06
  - Depends on: Phase 2 closed
  - Context: §4.4

Slug generation: `slugify(name)`, append `-2`, `-3` on collision. Slugs are immutable after `published_at` is set — changing one breaks existing links and SEO. Enforce this in `save()`.

- [x] **T3.1 — Catalog services** (2026-10-23, ea81176)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P3-V07, P3-V12
  - Depends on: T3.2
  - Context: §4.4 (the attribute-agnostic catalog)

`apps/catalog/services.py` — pure functions, no HTTP:

- `create_product(type_code, name, attributes, ...) -> Product` (validates attributes, generates the slug with the T3.2 rules)
- `add_variant(product, options, price_cents, sku, ...) -> Variant` (rejects options whose keys don't match the resolved `variant_axes`)
- `resolve_variant_axes(product) -> list[str]` (`product.variant_axes` if set, else `product_type.variant_axes`)
- `publish_product(product)` / `archive_product(product)`

- [x] **T3.3 — Catalog admin** (2026-10-23, b7a7c3c)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P3-V01, P3-V08
  - Depends on: T3.1
  - Context: §4.4

Admin registration:

- `ProductAdmin` with inline `VariantInline` and `ProductImageInline`.
- `list_display`: name, type, status, variant count, total available stock, price range.
- `list_filter`: status, product_type, franchise, brand.
- `search_fields`: name, variants' SKU.
- Actions: "Publicar", "Archivar", "Duplicar producto" (duplication matters — most new figures are near-copies of an existing one).

- [x] **T3.4 — Dynamic attributes widget** (2026-10-23, 614520c)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P3-V02, P3-V11
  - Depends on: T3.3
  - Context: §4.4 (the attribute-agnostic catalog)

Implement `apps/catalog/admin.py` with a dynamic `attributes` widget that renders one form field per schema property, typed by `"type"` (absorbs plan 2.6). This is the difference between a usable admin and a raw JSON textarea. Budget a day for it; it pays back every week.

Render each `attribute_schema` property as a typed field: `string` → text, `string` with `enum` → select, `integer`/`number` → number, `boolean` → checkbox. Fall back to a JSON textarea if the schema is unrecognised, never to a crash.

- [x] **T3.5 — Product images** (2026-10-24, 6bfa4eb)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P3-V04
  - Depends on: T3.3
  - Context: §4.3 (Boundaries: media storage)

Image handling: on upload, generate WebP derivatives at 400/800/1600px wide with Pillow and store all four keys through Django's default storage backend (`MEDIA_STORAGE=local` in Part A; object storage and CDN in Phase 18 — §4.3). App code uses `providers.media_store()`, never a storage class directly. Never serve originals.

- [x] **T3.6 — Catalog importer** (2026-10-24, be8ced0)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P3-V03, P3-V09, P3-V10
  - Depends on: T3.5, T3.1, T3.2
  - Context: §4.4; CR-49
  - Open items: G39 (follow the proposed resolution until decided); D12 (stand-in §2.5)

`manage.py import_catalog <file.csv>` — idempotent import keyed on SKU. Columns: `sku,product_slug,product_name,product_type,brand,franchise,categories,price_mxn,options_json,attributes_json,weight_grams,image_urls`. Dry-run flag that reports what would change and writes nothing. Needed for D12.

The file path is given at run time. A catalog file that holds costs is never committed to the repository (CR-49); tests use generated CSVs.

- [x] **T3.7 — Minimal demo seed** (2026-10-24, 48332e3)
  - Release: R1 · Gate: phase-close
  - REQs: —
  - Verifies: [no-test: a development seed; Phase 15 replaces it, and P15-V10 checks the full demo seed]
  - Depends on: T3.6
  - Context: §2.5

`manage.py seed_demo` — creates one product per launch type with realistic attributes, for local development and for the test suite. Phase 15 (T15.1) expands it into the full demo dataset.

#### Verify — test specification

> Every ID below is a named test (§4.6). The phase closes when every in-scope ID passes in `make test-all` (§0.2). ⚠️ G# marks a test written against a gap's proposed resolution, `xfail(strict=True, reason="G#")` until the gap is decided (§2.4). `[R2]` marks an ID outside Release 1; `[manual]` an ID checked by hand in the phase-close report.

**From the original Verify items:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P3-V01 | integration | `api/tests/integration/catalog/test_variants.py::test_p3_v01_apparel_six_variants_seventh_rejected` | `add_variant` creates the 6 S/M/L × negro/blanco combinations. A 7th duplicating S/negro raises a validation error (no `IntegrityError` leaks), and the admin inline returns a form error. |
| P3-V02 | integration | `api/tests/integration/catalog/test_admin_attributes.py::test_p3_v02_missing_required_attribute_field_error` | The admin add form for a `figure` without `numero` returns 200 with a field error on `numero`. There is no 500 and nothing is saved. |
| P3-V03 | integration | `api/tests/integration/catalog/test_import_catalog.py::test_p3_v03_dry_run_and_idempotent_import` | On a 50-row CSV: `--dry-run` reports 50 creates and the database is unchanged. A real run yields 50 products; a second run still yields 50 and reports 0 creates and 0 updates. |
| P3-V04 | integration | `api/tests/integration/catalog/test_images.py::test_p3_v04_three_webp_derivatives` | A 3000px JPEG produces WebP derivatives 400, 800 and 1600px wide via `providers.media_store()`. The API exposes no URL for the original. |

**Added negative and edge cases:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P3-V05 | unit | `api/tests/unit/catalog/test_slugs.py::test_p3_v05_slug_collision_suffix` | Three products with the same name get `x`, `x-2`, `x-3`. |
| P3-V06 | unit | `api/tests/unit/catalog/test_slugs.py::test_p3_v06_slug_immutable_after_publish` | Changing the slug before publishing is allowed; after `published_at` is set it raises a validation error. |
| P3-V07 | unit | `api/tests/unit/catalog/test_variants.py::test_p3_v07_options_must_match_axes` | Option keys outside the resolved axes are rejected; `product.variant_axes` overrides the type default. |
| P3-V08 | integration | `api/tests/integration/catalog/test_admin_actions.py::test_p3_v08_duplicate_product_action` | The copy gets a new slug, `status='draft'`, duplicated variants with new SKUs, and no stock rows. |
| P3-V09 | integration | `api/tests/integration/catalog/test_import_catalog.py::test_p3_v09_invalid_row_reported` | A row with invalid `attributes_json` or an unknown product type is reported with its row number and field. If any row is invalid, nothing is imported and every invalid row is reported (G12, ADR-0033). |
| P3-V10 | integration | `api/tests/integration/catalog/test_import_catalog.py::test_p3_v10_reimport_updates_price` | Re-importing with a changed price updates the variant and reports exactly 1 update. |
| P3-V11 | integration | `api/tests/integration/catalog/test_admin_attributes.py::test_p3_v11_unrecognised_schema_falls_back_to_json` | A schema property of an unsupported type renders as a JSON textarea; the page does not crash. |
| P3-V12 | unit | `api/tests/unit/catalog/test_publish.py::test_p3_v12_publish_and_archive` | `publish_product` sets `published_at` and `status='active'`; `archive_product` sets `archived` and keeps the slug. |

**Fixtures and factories introduced** (reused by later phases)

- `product_with_variants(type_code, combos)`, `apparel_hoodie` (6 variants), `nendoroid`
- `jpeg_image(width)` — a Pillow-generated in-memory JPEG
- `catalog_csv(rows)` — builds an import file in `tmp_path`
- `admin_client` — a Django test client logged in as a superuser

### Phase 4 — Inventory: stock, reservations, ledger

**Deliverable:** a correct, concurrency-safe inventory core with a test that proves two simultaneous checkouts cannot oversell the last unit.

**Release 1 scope:** all tasks except counter sales (T4.5, T4.10), which are R2. Adds receiving goods from the admin (T4.7), bin locations (T4.8) and the integrity command (T4.9).

**This is the highest-risk phase in the project. Do not rush it and do not skip the concurrency test.**

#### Core rules the code must enforce

1. `available(variant, location) = on_hand - reserved - safety_stock`, never negative (CR-04).
2. Every mutation of `on_hand` writes a `stock_ledger` row **in the same transaction**, with `balance_after` set (CR-05).
3. Reservations move `stock_item.reserved`, never `on_hand` (CR-06).
4. Every stock mutation acquires `SELECT ... FOR UPDATE` on the `stock_item` row first. No exceptions (CR-07).
5. Pre-order quantity is drawn from `variant.preorder_limit - variant.preorder_committed`, never from `stock_item` (CR-08; R2).

#### Tasks

Execution order: T4.2, T4.1, T4.3, T4.4, T4.9, T4.6, T4.7, T4.8 (phase-close, last); then, in R2, T4.10 and T4.5. T4.2 comes first because `reserve` (T4.1) raises `InsufficientStock`. IDs keep their numbers (OA-32).

- [x] **T4.2 — Insufficient-stock error** (2026-10-24, 4a45e76)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P4-V10
  - Depends on: Phase 3 closed
  - Context: "Core rules" above

`InsufficientStock` must carry the variant, requested quantity and available quantity, so the checkout API can return a precise message per line ("Solo quedan 2 de Nendoroid Link").

- [x] **T4.1 — Inventory services** (2026-10-24, 4f1e311)
  - Release: R1 · Gate: task
  - REQs: REQ-010, REQ-011, REQ-012, REQ-022
  - Verifies: P4-V01, P4-V02, P4-V05, P4-V06, P4-V09, P4-V11, P4-V12, P4-V13, P4-V15, P4-V16
  - Depends on: T4.2
  - Context: "Core rules" above; §4.4; §4.6 (Property-based, Concurrency)

`apps/inventory/services.py`:

```python
@transaction.atomic
def receive_stock(variant, location, qty, *, actor=None, note="") -> StockItem:
    """Goods received. on_hand += qty, ledger reason='receipt'."""

@transaction.atomic
def reserve(order, lines: list[tuple[Variant, int]], *, ttl: timedelta) -> list[InventoryReservation]:
    """Hold units for an order. Locks each stock_item FOR UPDATE, checks
    available >= qty, increments reserved, creates a 'held' reservation.
    Raises InsufficientStock(variant, requested, available) — never partially
    reserves. All or nothing."""

@transaction.atomic
def commit_reservations(order) -> None:
    """Payment settled. For each 'held' reservation of kind='stock':
    on_hand -= qty, reserved -= qty, ledger reason='sale_online',
    state -> 'committed'. For kind='preorder' (R2): state -> 'committed' only
    (preorder_committed was already incremented at reserve time)."""

@transaction.atomic
def release_reservations(order, *, reason: str) -> None:
    """Order cancelled or expired. reserved -= qty for 'stock' kind;
    preorder_committed -= qty for 'preorder' kind (R2). state -> 'released'.
    Idempotent: releasing an already-released reservation is a no-op."""

@transaction.atomic
def adjust_stock(variant, location, delta, *, reason, actor, note) -> None:
    """Manual correction, damage, count. Rejects a delta that would push
    on_hand below reserved."""
```

`record_in_store_sale` moves to T4.10 (R2).

- [x] **T4.3 — Reservation expiry job** (2026-10-24, 44b0c32)
  - Release: R1 · Gate: task
  - REQs: REQ-012
  - Verifies: P4-V03, P4-V08
  - Depends on: T4.1
  - Context: "Core rules" above; §4.8

`manage.py expire_reservations` — finds `inventory_reservation` rows where `state='held' AND expires_at < now()`, releases them, and transitions the owning order `pending_payment → expired`. Must be safe to run concurrently with a webhook approving the same order: take the order row `FOR UPDATE` and re-check state before acting. Add its line to `infra/crontab`: every 5 minutes (§4.8).

- [x] **T4.4 — Stock admin** (2026-10-24, 5ef9a2c)
  - Release: R1 · Gate: task
  - REQs: REQ-011
  - Verifies: P4-V18
  - Depends on: T4.3
  - Context: "Core rules" above

Admin: a read-only `StockLedger` view filtered by variant and date; a `StockItem` changelist with an inline "adjust" action that calls `adjust_stock` (never a raw editable `on_hand` field — that would bypass the ledger).

- [x] **T4.9 — Stock integrity command** (2026-10-24, e5e78de)
  - Release: R1 · Gate: task
  - REQs: REQ-011
  - Verifies: P4-V07
  - Depends on: T4.4
  - Context: "Core rules" above; §4.8

Per G24 (ADR-0034), the command is built here; Phase 21 (21.7) keeps only its production scheduling. `manage.py check_stock_integrity` asserts that for every `stock_item`, the sum of its ledger deltas equals `on_hand`, and that `reserved` equals the sum of `held` reservations. It exits non-zero, naming the stock item, when either fails. Add its daily line to `infra/crontab` (§4.8).

- [x] **T4.6 — Low-stock report and the outbox write helper** (2026-10-25, 5de8230)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P4-V17
  - Depends on: T4.9
  - Context: §4.4 (`email_outbox`); §4.8

Per G2's proposed resolution, add the `enqueue_email()` helper: it writes an `email_outbox` row in the caller's transaction and does not send. Sending arrives in Phase 11 (T11.1).

`manage.py low_stock_report` — emails the owner a list of variants with `available <= safety_stock`. Run daily: add its line to `infra/crontab` (§4.8).

- [x] **T4.7 — Receiving goods in the admin** (2026-10-25, a0a981e)
  - Release: R1 · Gate: task
  - REQs: REQ-064
  - Verifies: P4-V19
  - Depends on: T4.6
  - Context: "Core rules" above; GE:T30

Per G20's proposed resolution, add a "Recibir mercancía" admin action: the staff member picks the variant and location and enters a quantity, and the action calls `receive_stock` with the staff user as `actor`. A zero or negative quantity is a form error. `on_hand` is never an editable field. The pre-order path (`receive_preorder_stock`, 10.3) is R2.

- [x] **T4.8 — Bin locations** (2026-10-25, 8befc86)
  - Release: R1 · Gate: phase-close
  - REQs: REQ-064
  - Verifies: P4-V20
  - Depends on: T4.7, T4.4
  - Context: §4.4 (pending schema changes)

Per G34's resolution (ADR-0030), `stock_item.bin_location` is an optional text field created in T2.1b. It is editable in the `StockItem` admin without touching `on_hand`, and writing no ledger row. The packing view that shows it is T10.17.

- [ ] **T4.10 — Counter-sale service**
  - Release: R2 · Gate: —
  - REQs: REQ-010
  - Verifies: P4-V04, P4-V14
  - Depends on: Phase 4 closed
  - Context: "Core rules" above; A11

Add to `apps/inventory/services.py`:

```python
@transaction.atomic
def record_in_store_sale(location, lines, *, staff_user, note="") -> InStoreSale:
    """Counter sale (A11). on_hand -= qty, ledger reason='sale_in_store'.
    Rejects if it would violate reserved <= on_hand — meaning the units are
    already promised to an online order. The staff member must then decide:
    cancel the online order, or refuse the counter sale."""
```

Extend the inventory machine (P4-V06) with `record_in_store_sale` (§4.6).

- [ ] **T4.5 — Counter-sale page**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: [no-test: the plan has no Verify item for this page; add one when R2 is planned]
  - Depends on: T4.10
  - Context: "Core rules" above; A11

Admin: an "Registrar venta en tienda" page — pick location, scan/type SKUs, quantities, save. Calls `record_in_store_sale`. This page is how the site stays the source of truth for physical stock. Make it fast to use; it will be used daily.

#### Verify — test specification

> Every ID below is a named test (§4.6). The phase closes when every in-scope ID passes in `make test-all` (§0.2). ⚠️ G# marks a test written against a gap's proposed resolution, `xfail(strict=True, reason="G#")` until the gap is decided (§2.4). `[R2]` marks an ID outside Release 1; `[manual]` an ID checked by hand in the phase-close report.

**From the original Verify items:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P4-V01 | concurrency | `api/tests/concurrency/test_reserve.py::test_p4_v01_concurrent_reserve_last_unit` | `on_hand=1`; two threads call `reserve` behind a barrier. Exactly one reservation exists; the other thread got `InsufficientStock`; `reserved == 1`. |
| P4-V02 | integration | `api/tests/integration/inventory/test_reservations.py::test_p4_v02_commit_moves_stock_and_writes_ledger` | Reserve 2, then commit: `on_hand` drops by 2, `reserved` returns to 0, one ledger row `sale_online` with `delta=-2` and the correct `balance_after`, and the reservation is `committed`. |
| P4-V03 | integration | `api/tests/integration/inventory/test_reservations.py::test_p4_v03_expired_hold_leaves_no_ledger` | Reserve 2, advance the clock past `expires_at`, run `expire_reservations`: `reserved` is 0, there is **no** ledger row, the reservation is `released`. From Phase 8 (T8.6a) the test also asserts the order is `expired` (G37). |
| P4-V04 [R2] | integration | `api/tests/integration/inventory/test_counter_sale.py::test_p4_v04_counter_sale_cannot_take_reserved_unit` | With `on_hand=1, reserved=1`, `record_in_store_sale` raises with a message naming the pending order; `on_hand` is unchanged. |
| P4-V05 | integration | `api/tests/integration/inventory/test_reservations.py::test_p4_v05_release_idempotent` | A second `release_reservations` changes nothing and raises nothing. |
| P4-V06 | property | `api/tests/property/test_inventory_machine.py::test_p4_v06_ledger_sum_equals_on_hand` | The stateful machine (§4.6) holds all its inventory invariants after every step. |
| P4-V07 | integration | `api/tests/integration/inventory/test_integrity_command.py::test_p4_v07_check_stock_integrity` | `check_stock_integrity` exits 0 on clean data and non-zero, naming the stock item, after a raw-SQL change to `on_hand`. |

**Added negative and edge cases:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P4-V08 | integration | `api/tests/integration/inventory/test_reservations.py::test_p4_v08_ttl_boundary` | At `now == expires_at` the hold is **not** released; at `expires_at + 1µs` it is (rule `expires_at < now()`). |
| P4-V09 | integration | `api/tests/integration/inventory/test_reservations.py::test_p4_v09_reserve_all_or_nothing` | A two-line reserve whose second line is short raises `InsufficientStock` for that line and leaves the first line unreserved. |
| P4-V10 | unit | `api/tests/unit/inventory/test_errors.py::test_p4_v10_insufficient_stock_payload` | `InsufficientStock` carries the variant, the requested quantity and the available quantity. |
| P4-V11 | integration | `api/tests/integration/inventory/test_reservations.py::test_p4_v11_safety_stock_respected` | With `on_hand=5, safety_stock=2`, reserving 3 succeeds and reserving 4 fails. |
| P4-V12 | integration | `api/tests/integration/inventory/test_adjust.py::test_p4_v12_adjust_below_reserved_rejected` | With `on_hand=3, reserved=2`, `delta=-2` is rejected and `delta=-1` succeeds; the ledger row records reason, note and actor. |
| P4-V13 | unit | `api/tests/unit/inventory/test_validation.py::test_p4_v13_invalid_quantity` | Quantity 0 or negative is rejected before any query runs (`django_assert_num_queries(0)`). |
| P4-V14 [R2] | concurrency | `api/tests/concurrency/test_counter_sale.py::test_p4_v14_counter_sale_vs_checkout` | For the last unit, a counter sale and a reservation race: exactly one succeeds, and the invariants hold. |
| P4-V15 | integration | `api/tests/integration/inventory/test_ledger.py::test_p4_v15_every_on_hand_change_has_one_ledger_row[reason]` | `receipt`, `sale_online`, `adjustment`, `damage` and `count_correction` each write exactly one row with that reason. (`sale_in_store` is covered by P10-V11, R2.) |
| P4-V16 | integration | `api/tests/integration/inventory/test_reservations.py::test_p4_v16_commit_twice` | Calling `commit_reservations` twice is a no-op the second time (G15). |
| P4-V17 | integration | `api/tests/integration/inventory/test_low_stock.py::test_p4_v17_low_stock_report_boundary` | A variant with `available == safety_stock` is included; `safety_stock + 1` is excluded; an `email_outbox` row is written, addressed to the owner's alert address (`OWNER_ALERT_EMAIL`). |
| P4-V18 | integration | `api/tests/integration/inventory/test_admin.py::test_p4_v18_no_editable_on_hand` | The `StockItem` admin form has no editable `on_hand`; its adjust action goes through `adjust_stock`. |

**Added in conversion:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P4-V19 | integration | `api/tests/integration/inventory/test_receiving.py::test_p4_v19_receive_goods_admin_action` | The "Recibir mercancía" admin action records a receipt through `receive_stock`: `on_hand` rises by the quantity, and one `receipt` ledger row names the staff user. A zero or negative quantity shows a form error and changes nothing. |
| P4-V20 | integration | `api/tests/integration/inventory/test_admin.py::test_p4_v20_bin_location_editable` | A stock item's bin location can be edited in the admin without touching `on_hand`; the edit writes no ledger row. |

**Fixtures and factories introduced** (reused by later phases)

- `StockItemFactory`; `stocked_variant(on_hand, safety_stock=0, location=warehouse)`
- `DraftOrderFactory` — a `draft` order only. State traits arrive in Phase 8 through `order_in_state`
- `holding_order(variant, qty, ttl)` — a draft order with a `held` reservation, built through `reserve()`
- `InventoryMachine` — the hypothesis `RuleBasedStateMachine`; R2 extends it with counter sales (T4.10) and pre-order rules (Phase 10)
- `assert_stock_integrity(variant)` — the invariant checks as a reusable assertion
- `outbox` — reads `email_outbox` rows; nothing is rendered or sent until Phase 11

### Phase 5 — Public catalog API

**Deliverable:** read-only endpoints the storefront can build on, with an OpenAPI schema and generated TypeScript types, and a pre-launch mode that hides the catalog from the public.

**Release 1 scope:** all tasks, plus pre-launch mode on the API (T5.7). Pickup and pre-order availability are R2 (T5.8).

#### Tasks

Execution order: T5.3, T5.1, T5.2, T5.4, T5.5, T5.6, T5.7 (phase-close, last); then, in R2, T5.8. T5.3 comes first because the list and detail endpoints (T5.1) filter and report by availability, and P5-V01 (T5.2) combines an attribute filter with `in_stock`. The facets endpoint and P5-V13 move from T5.1 to T5.2, which builds the filters they count. IDs keep their numbers (OA-39).

- [x] **T5.3 — Availability** (2026-10-25, 47b9707)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P5-V07, P5-V08
  - Depends on: Phase 4 closed
  - Context: "Core rules" of Phase 4

Availability in the serializer, shaped by D10 (ADR-0037). Release 1 payload:

```json
{"status": "in_stock" | "low_stock" | "out_of_stock"}
```

Do not expose raw counts (D10, ADR-0037). `low_stock` when `1 <= available <= 5`. Release 2 adds the `preorder` status, `preorder_release_date` and `pickup_available` (T5.8).

- [x] **T5.1 — Catalog endpoints** (2026-10-25, 57b9219)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P5-V05, P5-V09, P5-V12
  - Depends on: T5.3
  - Context: §4.4 (the attribute-agnostic catalog)

Endpoints (all under `/api/`, all read-only, all cacheable):

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/catalog/products/` | List. Filters: `category`, `franchise`, `brand`, `type`, `q`, `min_price`, `max_price`, `in_stock` (the dynamic `attr.<key>` filters are T5.2; the `preorder` filter is R2). Cursor pagination. |
| GET | `/api/catalog/products/{slug}/` | Detail with variants, images, availability, related products (G28, ADR-0030: products that share the franchise or a category). |
| GET | `/api/catalog/categories/` | Tree. |
| GET | `/api/catalog/search/?q=` | Full-text over `search_tsv` with trigram fallback for typos. |

The facets endpoint (`/api/catalog/facets/`) is built in T5.2, with the attribute filters it counts. `in_stock` and the `availability` field use the availability built in T5.3.

- [x] **T5.2 — Attribute filters** (2026-10-25, 7f5d0cf)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P5-V01, P5-V02, P5-V06, P5-V13
  - Depends on: T5.1
  - Context: §4.4 (the attribute-agnostic catalog)

Dynamic attribute filtering: translate `?attr.linea=Nendoroid` into `attributes @> '{"linea":"Nendoroid"}'` using a parameterised query. **Whitelist the key against `product_type.filterable_keys`** before building the query — never interpolate a user-supplied key into SQL.

Then add `GET /api/catalog/facets/`: the available filter values for the current query, driven by `product_type.filterable_keys`. The counts reflect every active filter, including `attr.*`.

- [x] **T5.4 — Query performance** (2026-10-25, d3bd746)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P5-V03
  - Depends on: T5.2
  - Context: §4.6 (API)

`select_related` on type/brand/franchise, `prefetch_related` on variants, images, and stock items. Assert the product list endpoint issues a bounded number of queries regardless of page size — add `django-zen-queries` or an explicit `assertNumQueries` test. N+1 on the catalog list is the most likely performance bug in this system.

- [x] **T5.5 — OpenAPI schema and generated types** (2026-10-25, bcb0d9b)
  - Release: R1 · Gate: task
  - REQs: REQ-054
  - Verifies: P5-V04, P5-V11
  - Depends on: T5.4
  - Context: §4.6 (Contract — OpenAPI); CR-25

`drf-spectacular` configured; `/api/schema/` serves OpenAPI 3.1. Add `pnpm gen:api` in `web/` running `openapi-typescript ../api/openapi.snapshot.yml -o app/types/api.d.ts`. Generating from the committed snapshot rather than a running server keeps it offline and deterministic; the snapshot test (§4.6) guarantees the snapshot matches the live schema. `make schema-update` runs both steps.

- [x] **T5.6 — Catalog caching** (2026-10-25, 8617066)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P5-V10
  - Depends on: T5.5
  - Context: §4.1

Cache `GET /api/catalog/*` responses with `Cache-Control: public, max-age=60` and let the CDN absorb the traffic. Bust nothing; 60 seconds of staleness on a catalog page is fine. Availability is re-checked at add-to-cart and again at checkout, so a stale badge cannot cause an oversell.

- [x] **T5.7 — Pre-launch mode on the API** (2026-10-25, 67b2701)
  - Release: R1 · Gate: phase-close
  - REQs: REQ-062
  - Verifies: P5-V15
  - Depends on: T5.6
  - Context: §1.2 (pre-launch catalog mode); §7.1 (R-19); GE:T31
  - Open items: —

Per G32 (ADR-0038), add a site-wide pre-launch switch, turned off by staff when the store goes live. While it is on, anonymous requests to `/api/catalog/*` get the pre-launch response and never `Cache-Control: public`, so the CDN cannot cache the hidden catalog. Requests from a logged-in staff session get the normal catalog with `Cache-Control: private`. The switch is the `prelaunch_mode` boolean of the single-row table `site_setting`, edited in the admin, so staff turn it on and off without a deploy; it is off until staff turn it on. The pre-launch response is `503` with the JSON body `{"prelaunch": true}` and `Cache-Control: no-store`. The `prelaunch_on` fixture sets the row. The storefront page is T12.15.

- [ ] **T5.8 — Pickup and pre-order availability**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P5-V14, P5-V16
  - Depends on: Phase 5 closed
  - Context: 10.A

Add to the availability payload the `preorder` status, `preorder_release_date`, and `pickup_available` (true only when the variant is available at an `is_pickup_point` location), and the `preorder` list filter:

```json
{"status": "in_stock" | "low_stock" | "out_of_stock" | "preorder",
 "preorder_release_date": "2026-11-15" | null,
 "pickup_available": true}
```

#### Verify — test specification

> Every ID below is a named test (§4.6). The phase closes when every in-scope ID passes in `make test-all` (§0.2). ⚠️ G# marks a test written against a gap's proposed resolution, `xfail(strict=True, reason="G#")` until the gap is decided (§2.4). `[R2]` marks an ID outside Release 1; `[manual]` an ID checked by hand in the phase-close report.

**From the original Verify items:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P5-V01 | API | `api/tests/api/catalog/test_product_list.py::test_p5_v01_attr_filter_and_in_stock` | `?attr.linea=Nendoroid&in_stock=true` returns exactly the active Nendoroids with `available > 0`. |
| P5-V02 | API | `api/tests/api/catalog/test_product_list.py::test_p5_v02_malicious_attr_keys_rejected` | `attr.__proto__=x` and `attr.'; DROP TABLE product;--=1` return 400, and no product query executes. |
| P5-V03 | API | `api/tests/api/catalog/test_product_list.py::test_p5_v03_query_count_bounded` | `django_assert_max_num_queries(9)` holds for pages of 24 and of 48 items (no N+1). |
| P5-V04 | contract | `api/tests/contract/openapi/test_snapshot.py::test_p5_v04_serializer_rename_breaks_snapshot` | Renaming a product serializer field (monkeypatched) makes the generated schema differ from the snapshot. *The frontend-build half of the original item is P12-V04.* |
| P5-V05 | integration | `api/tests/integration/catalog/test_search.py::test_p5_v05_fulltext_and_trigram` | "nendoroid zelda" and "nendorid zelda" both return the product; a name match ranks above a description match. |

**Added negative and edge cases:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P5-V06 | API | `api/tests/api/catalog/test_product_list.py::test_p5_v06_non_filterable_key_rejected` | An attribute key not in `filterable_keys` returns 400. |
| P5-V07 | API | `api/tests/api/catalog/test_availability.py::test_p5_v07_status_boundaries[available]` | `0 → out_of_stock`; `1` and `5 → low_stock`; `6 → in_stock`. |
| P5-V08 | API | `api/tests/api/catalog/test_availability.py::test_p5_v08_no_raw_counts_exposed` | No response contains `on_hand`, `reserved` or a numeric availability (D10). |
| P5-V09 | API | `api/tests/api/catalog/test_product_detail.py::test_p5_v09_draft_and_archived_hidden` | Draft and archived products are absent from the list and return 404 on detail. |
| P5-V10 | API | `api/tests/api/catalog/test_caching.py::test_p5_v10_cache_control` | Catalog GETs send `Cache-Control: public, max-age=60`; cart and order endpoints do not. |
| P5-V11 | contract | `api/tests/contract/openapi/test_schemathesis.py::test_p5_v11_catalog_fuzz` | Catalog endpoints never return 5xx and every response conforms to the schema. |
| P5-V12 | API | `api/tests/api/catalog/test_pagination.py::test_p5_v12_cursor_stable` | Walking every cursor page returns each product exactly once, even when a product is published midway. |
| P5-V13 | API | `api/tests/api/catalog/test_facets.py::test_p5_v13_facets_follow_filterable_keys` | Facet keys equal the type's `filterable_keys`; the counts reflect the current query. |
| P5-V14 [R2] | API | `api/tests/api/catalog/test_availability.py::test_p5_v14_pickup_available_flag` | `pickup_available` is true only when the variant is available at an `is_pickup_point` location. |

**Added in conversion:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P5-V15 | API | `api/tests/api/catalog/test_prelaunch.py::test_p5_v15_prelaunch_hides_catalog` | With pre-launch mode on, anonymous catalog requests get the pre-launch response and never `Cache-Control: public`; a staff session gets the catalog with `Cache-Control: private`. With the mode off, P5-V10 holds. |
| P5-V16 [R2] | API | `api/tests/api/catalog/test_availability.py::test_p5_v16_preorder_status` | A pre-order variant has status `preorder` with its `preorder_release_date`. |

**Fixtures and factories introduced** (reused by later phases)

- `catalog_dataset` — products across the launch types; stock at each availability boundary; one draft, one archived, one pre-order (used by R2 items)
- `search_corpus` — products with overlapping names for ranking and trigram tests
- `schemathesis_schema` — the in-process schema loaded from the WSGI app, reused by every later API phase
- `prelaunch_on` — turns the pre-launch switch on for one test

### Phase 6 — Customer accounts

**Deliverable:** Release 1: the postal-code lookup, the guest order lookup, and the session and CSRF settings that staff sessions and the cart rely on, all on one origin. Release 2 adds registration, email verification, login, password reset, saved addresses, order history and guest-order claiming, with session-cookie auth.

**Release 1 scope:** the cookie and CSRF settings (6.2), the postal-code lookup (6.6) and the guest order lookup (6.7b); everything else is Release 2.

#### Tasks

- [x] **T6.2 — Session cookie and CSRF settings** (2026-10-25, 6e6879a)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P6-V16
  - Depends on: Phase 5 closed
  - Context: §4.1, §4.6 (API)

Cookie settings: `HttpOnly`, `Secure`, `SameSite=Lax`, `SESSION_COOKIE_AGE = 60*60*24*30`. CSRF: Django's `CsrfViewMiddleware` stays on; Nuxt reads the `csrftoken` cookie and sends `X-CSRFToken` on every unsafe method. Same-origin makes this work without configuration gymnastics.

In Release 1 the session belongs to staff signed in to the admin, whose session the storefront also forwards for the pre-launch catalog (G32). Customer sessions arrive with T6.1 in Release 2. The cart endpoints (Phase 7) and checkout (Phase 8) use the same CSRF scheme for every unsafe method (P7-V18).

- [x] **T6.6 — Postal-code lookup** (2026-10-25, deadc8a)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P6-V13
  - Depends on: Phase 5 closed
  - Context: §4.3 (Boundaries: postal codes), §4.7
  - Open items: —

`GET /api/postal-codes/{cp}/` → `{state_code, state_name, municipality, neighborhoods: [...]}` via `providers.postal_code_lookup()` (§4.3), backed by `mx_postal_code`. Cache aggressively. This turns a 6-field address form into "type your CP, pick your colonia", which is the single biggest usability win in Mexican checkout.

Also build `manage.py load_postal_codes`, which reads `POSTAL_CODE_DATASET` and a file path and never makes a network call (§4.3). Part A loads the committed sample fixture; the full SEPOMEX load is a Phase 22 data task. If a code is missing, the form degrades to free text (P13-V06). The full dataset is a launch requirement; the sample stays for Part A (G30, ADR-0039).

- [x] **T6.7b — Guest order lookup** (2026-10-25, b7ca64b)
  - Release: R1 · Gate: phase-close
  - REQs: —
  - Verifies: P6-V14, P6-V18
  - Depends on: T6.2, T6.6
  - Context: §4.6 (API)
  - Open items: —

Per G35 (ADR-0040): `POST /api/orders/lookup/` with the JSON body `{number, email}`, rate-limited to 5 per hour per IP with `django-ratelimit` (added to the dependencies here). A guest with the order number and the email on the order can see its status without an account: the email never goes in the URL, so proxy, CDN and error logs cannot record it. The response is the order status serializer (state, lines, totals, the tracking link, and the pending voucher once 9.6 adds it). A wrong email and a missing order return the same 404 body.

- [ ] **T6.1 — Auth endpoints**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P6-V01, P6-V04, P6-V08, P6-V09, P6-V10
  - Depends on: T6.2, T4.6
  - Context: §4.1, §4.6 (API)

Auth endpoints (DRF views over Django's session framework — **not** JWT, **not** DRF TokenAuth):

| Method | Path | Notes |
|---|---|---|
| POST | `/api/auth/register/` | email, password, full_name. Creates unverified customer, queues verification email. |
| POST | `/api/auth/login/` | Sets session cookie. |
| POST | `/api/auth/logout/` | |
| GET | `/api/auth/me/` | Current customer or 401. |
| POST | `/api/auth/verify-email/` | Token from email. |
| POST | `/api/auth/resend-verification/` | Rate-limited. |
| POST | `/api/auth/password-reset/` | Always returns 200, whether or not the email exists. |
| POST | `/api/auth/password-reset/confirm/` | |
| PATCH | `/api/auth/me/` | Update name, phone, marketing consent. |
| POST | `/api/auth/change-password/` | Requires current password. |

The verification and reset emails are queued through the outbox write helper (T4.6, G2).

- [ ] **T6.3 — Password rules and lockout**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P6-V03, P6-V17
  - Depends on: T6.1
  - Context: §4.6 (API)

Password rules: Django's default validators plus `MinimumLengthValidator(10)`. Do not invent composition rules — length beats symbol soup. `django-axes` locks an account after 5 failed attempts in 15 minutes.

- [ ] **T6.4 — Account rate limits**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P6-V11
  - Depends on: T6.1
  - Context: §4.6 (API)

Rate limits, per IP and per email: register 5/hour, login 10/15min, password reset 3/hour, resend verification 3/hour. Use `django-ratelimit`. The guest-lookup limit is Release 1 and lives in T6.7b.

- [ ] **T6.5 — Address endpoints**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P6-V05, P6-V07, P6-V12
  - Depends on: T6.1
  - Context: §4.4, §4.6 (API)

Address endpoints: `GET/POST /api/addresses/`, `PATCH/DELETE /api/addresses/{id}/`, `POST /api/addresses/{id}/default/`. Deletion is a soft delete (`deleted_at`) because orders reference the address only as a frozen snapshot, but the customer may still want undo. Enforce a cap of 10 active addresses.

- [ ] **T6.7a — Customer order history**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P6-V06
  - Depends on: T6.1
  - Context: §4.6 (API)

Order history: `GET /api/orders/` (the customer's own, paginated) and `GET /api/orders/{public_id}/`.

- [ ] **T6.8 — Guest-order claiming**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P6-V02, P6-V15
  - Depends on: T6.7a
  - Context: §4.6 (API)

Guest-order claiming: after a verified customer logs in, offer to attach past guest orders sharing their email. **Only after `email_verified_at` is set** — otherwise registering with someone else's address exposes their order history. Implement as an explicit `POST /api/orders/claim/`, never automatically on login.

Execution order: T6.2, T6.6, T6.7b (phase-close, last of Release 1); then, in R2, T6.1, T6.3, T6.4, T6.5, T6.7a, T6.8. T6.1 was listed first but depends on T6.2 and is R2. T6.3, T6.4, T6.5 and T6.7a depend on T6.1 and can run in any order; T6.8 depends on T6.7a. IDs keep their numbers (OA-42).

#### Verify — test specification

> Every ID below is a named test (§4.6). The phase closes when every in-scope ID passes in `make test-all` (§0.2). ⚠️ G# marks a test written against a gap's proposed resolution, `xfail(strict=True, reason="G#")` until the gap is decided (§2.4). `[R2]` marks an ID outside Release 1; `[manual]` an ID checked by hand in the phase-close report.

**From the original Verify items:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P6-V01 [R2] | API | `api/tests/api/accounts/test_registration.py::test_p6_v01_register_verify_login_me` | Register → a `verify_email` `email_outbox` row with a token → verify → log in → `GET /api/auth/me/` returns the customer. |
| P6-V02 [R2] | API | `api/tests/api/accounts/test_claim.py::test_p6_v02_unverified_cannot_claim` | An unverified customer can log in and browse; `POST /api/orders/claim/` returns 403 and attaches nothing. |
| P6-V03 [R2] | API | `api/tests/api/accounts/test_login.py::test_p6_v03_lockout_after_failures` | After 5 failed logins, the next attempt is refused even with the correct password; the clock advanced 15 minutes clears it. |
| P6-V04 [R2] | API | `api/tests/api/accounts/test_password_reset.py::test_p6_v04_no_enumeration` | An unknown email returns 200 with a body identical to a known email's, and no outbox row is written. |
| P6-V05 [R2] | API | `api/tests/api/accounts/test_csrf.py::test_p6_v05_csrf_required` | `POST /api/addresses/` without `X-CSRFToken` returns 403. |
| P6-V06 [R2] | API | `api/tests/api/accounts/test_order_access.py::test_p6_v06_other_customers_order_404` | Customer B's order returns 404 to customer A, with the same body as a nonexistent id. |
| P6-V07 [R2] | API | `api/tests/api/accounts/test_addresses.py::test_p6_v07_new_default_clears_old` | Setting a second default leaves exactly one default. |

**Added negative and edge cases:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P6-V08 [R2] | API | `api/tests/api/accounts/test_registration.py::test_p6_v08_email_case_insensitive` | `Ana@X.com` is rejected when `ana@x.com` exists; login succeeds with either casing. |
| P6-V09 [R2] | API | `api/tests/api/accounts/test_verification.py::test_p6_v09_token_single_use_and_expiry` | A reused verification token returns 400; an expired one returns 400. |
| P6-V10 [R2] | API | `api/tests/api/accounts/test_password_reset.py::test_p6_v10_reset_token_single_use` | A reset token stops working once the password has changed. |
| P6-V11 [R2] | API | `api/tests/api/accounts/test_rate_limits.py::test_p6_v11_rate_limit_boundaries[endpoint]` | Per 6.4, the limit-th request succeeds and the next returns 429: register 5/h, login 10/15 min, reset 3/h, resend 3/h. The window resets after the period. *The guest-lookup case is P6-V18.* |
| P6-V12 [R2] | API | `api/tests/api/accounts/test_addresses.py::test_p6_v12_address_cap` | 10 active addresses are allowed and the 11th is rejected; soft-deleted addresses neither count nor appear in the list. |
| P6-V13 | API | `api/tests/api/accounts/test_postal_codes.py::test_p6_v13_postal_lookup` | A sample CP returns state, municipality and neighborhoods; an unknown CP returns 404; a malformed one returns 400. |
| P6-V14 | API | `api/tests/api/accounts/test_guest_lookup.py::test_p6_v14_guest_lookup` | Order number with the matching email returns the order; a wrong email returns the same 404 as a missing order. |
| P6-V15 [R2] | API | `api/tests/api/accounts/test_claim.py::test_p6_v15_claim_only_matching_email` | A verified customer claims only guest orders with their email — not other customers' orders, and not other emails. |
| P6-V16 | integration | `api/tests/integration/accounts/test_cookies.py::test_p6_v16_session_cookie_flags` | Under `prod.py`: `HttpOnly`, `Secure`, `SameSite=Lax`, and a 30-day age. |
| P6-V17 [R2] | unit | `api/tests/unit/accounts/test_passwords.py::test_p6_v17_min_length` | A 9-character password is rejected and a 10-character one accepted. |

**Added in conversion:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P6-V18 | API | `api/tests/api/accounts/test_guest_lookup.py::test_p6_v18_guest_lookup_rate_limit` | The 5th guest lookup in an hour from one IP succeeds and the 6th returns 429; the window resets after an hour. |

**Fixtures and factories introduced** (reused by later phases)

- `verified_customer`, `unverified_customer`, `logged_in_client(customer)` — Release 2
- `guest_order(email)` — a draft order with no customer; state traits come in Phase 8
- `postal_codes` — loads `api/fixtures/mx_postal_codes_sample.csv`

### Phase 7 — Cart and shipping quotes

**Deliverable:** a server-side cart that revalidates prices and stock and quotes delivery shipping. Release 2 adds the merge on login, pickup and pre-order rules.

**Release 1 scope:** delivery only; no merge on login, no pickup, no pre-order lines.

#### Tasks

- [x] **T7.9 — Totals in one function** (2026-10-25, 0293a7b)
  - Release: R1 · Gate: task
  - REQs: REQ-001, REQ-002
  - Verifies: P7-V06, P7-V17
  - Depends on: Phase 6 closed
  - Context: §4.6 (Property-based); A2

Totals live in exactly one function, `orders/pricing.py::compute_totals(lines, shipping_cents, discount_cents)`, returning subtotal, shipping, discount, total, and `tax_included_cents = round(total * 16 / 116)`. The cart endpoint, the checkout endpoint and the order creation path all call it. Never duplicate this arithmetic (CR-02).

- [x] **T7.7 — Shipping zones and rates seed** (2026-10-25, 33b9a08)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: [no-test: seed data; the quote tests of T7.6 assert the seeded shape]
  - Depends on: Phase 6 closed
  - Context: §2.5
  - Open items: D5 (stand-in §2.5)

Seed `shipping_zone`, `shipping_zone_state`, `shipping_rate` from D5. In Part A, `manage.py seed_dev_defaults` seeds the placeholder shape in §2.5; replace it before production.

- [x] **T7.2a — Cart identity** (2026-10-25, 6c0eb50)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: [no-test: exercised by every cart API test from T7.1 on; T7.1 owns the isolation test]
  - Depends on: Phase 6 closed
  - Context: §4.1

Cart identity: an opaque `cart_token` cookie (`HttpOnly`, `SameSite=Lax`, 30 days). A request without a valid token gets a new cart on its first write.

- [x] **T7.1 — Cart endpoints** (2026-10-25, 28b77e6)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P7-V10, P7-V16, P7-V18
  - Depends on: T7.9, T7.2a
  - Context: §4.6 (API)

Cart endpoints:

| Method | Path | Notes |
|---|---|---|
| GET | `/api/cart/` | Returns lines, live prices, per-line availability, totals, and a quote if `fulfillment_method` is set. |
| POST | `/api/cart/lines/` | `{variant_public_id, quantity}`. Upserts. Validates against `available`. |
| PATCH | `/api/cart/lines/{id}/` | Change quantity. |
| DELETE | `/api/cart/lines/{id}/` | |
| POST | `/api/cart/fulfillment/` | R1: `{method: "delivery", postal_code}` → recomputes shipping (wired in T7.6). R2 adds `"pickup"` with `pickup_location_id`. |

Every unsafe method requires `X-CSRFToken` (T6.2).

- [x] **T7.3 — Live prices, never stored** (2026-10-25, edd4a71)
  - Release: R1 · Gate: task
  - REQs: REQ-002
  - Verifies: P7-V03
  - Depends on: T7.1
  - Context: §4.1; CR-03

**The cart stores no prices.** `cart_line` holds only `variant_id` and `quantity`. Every `GET /api/cart/` reads the current `variant.price_cents`. Prices are frozen exactly once: when the order is created at checkout. This eliminates an entire class of stale-price bugs and disputes.

- [x] **T7.4 — Per-line availability** (2026-10-25, f5220cb)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P7-V02, P7-V11
  - Depends on: T7.3
  - Context: §4.6 (API)

Per-line availability in the cart response: `ok`, `reduced` (fewer available than requested — return `max_available`), or `unavailable`. Release 2 adds `preorder`. The cart never silently changes quantities; it reports and lets the customer decide.

- [x] **T7.6 — Shipping quote** (2026-10-25, e971c8f)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P7-V04, P7-V05, P7-V08, P7-V09
  - Depends on: T7.7, T7.4
  - Context: §4.3 (Boundaries: postal codes)

`apps/shipping/services.py::quote(postal_code, subtotal_cents) -> ShippingQuote`:

1. `postal_code` → `state_code` via `providers.postal_code_lookup()` (fallback: ask the customer for the state).
2. `state_code` → `zone_id` via `shipping_zone_state`.
3. Pick the `shipping_rate` for that zone whose `[min_subtotal_cents, max_subtotal_cents)` bracket contains the subtotal.
4. Return `{price_cents, eta_min_days, eta_max_days, name, zone}`.

Unknown postal code → 400 with a clear message, never a silent zero. Wire `POST /api/cart/fulfillment/` (T7.1) to this service. In Release 2, pickup always quotes `price_cents = 0` (enforced by the `order_pickup_has_no_shipping_fee` constraint).

- [x] **T7.5a — Lines that need no shipping** (2026-10-25, 4556332)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: [no-test: a constraint on T7.1 and T7.6 that no plan Verify item isolates; the default path is covered by the tests of T7.3 and T7.4]
  - Depends on: T7.6
  - Context: §4.1

A cart with any `requires_shipping=false` line still behaves normally (v1 has no digital goods, but don't hard-code the assumption).

- [x] **T7.8 — Stale cart purge** (2026-10-25, 5795eea)
  - Release: R1 · Gate: phase-close
  - REQs: —
  - Verifies: P7-V15
  - Depends on: T7.5a
  - Context: §4.8

`manage.py purge_stale_carts` — delete unconverted carts untouched for 60 days. Run weekly: add its line to `infra/crontab` (§4.8).

- [ ] **T7.2b — Cart merge on login**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P7-V01, P7-V12
  - Depends on: T6.1, T7.2a
  - Context: §4.6 (API)

On login, if the anonymous cart has lines, merge into the customer's existing cart (sum quantities, clamp to available); otherwise adopt it. Always delete the anonymous cart after merge.

- [ ] **T7.5b — Mixed-cart and pickup rules**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P7-V07, P7-V13, P7-V14
  - Depends on: T7.5a
  - Context: 10.A; A6

Mixed-cart rules:

- A cart mixing pre-order and in-stock items is **allowed** and ships complete (A6, confirm D8). The cart response must say so plainly: *"Tu pedido se enviará completo a partir del 15 de noviembre."*
- Pickup is offered only if every line has `available > 0` at a `is_pickup_point` location, **or** is a pre-order. Pre-order pickup is fine — it just waits.

Execution order: T7.9, T7.7, T7.2a, T7.1, T7.3, T7.4, T7.6, T7.5a, T7.8 (phase-close, last of Release 1); then, in R2, T7.2b and T7.5b. IDs keep their numbers (OA-45). T7.1 builds the cart endpoints; the `GET /api/cart/` and `POST /api/cart/fulfillment/` payloads grow with T7.3 (live prices), T7.4 (availability) and T7.6 (the quote).

#### Verify — test specification

> Every ID below is a named test (§4.6). The phase closes when every in-scope ID passes in `make test-all` (§0.2). ⚠️ G# marks a test written against a gap's proposed resolution, `xfail(strict=True, reason="G#")` until the gap is decided (§2.4). `[R2]` marks an ID outside Release 1; `[manual]` an ID checked by hand in the phase-close report.

**From the original Verify items:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P7-V01 [R2] | API | `api/tests/api/carts/test_merge.py::test_p7_v01_anonymous_cart_survives_login` | Lines are preserved after login, and the anonymous cart is deleted. |
| P7-V02 | API | `api/tests/api/carts/test_lines.py::test_p7_v02_reduced_not_mutated` | Requesting 3 when 2 are available reports `reduced` with `max_available: 2`; the stored quantity stays 3. |
| P7-V03 | API | `api/tests/api/carts/test_pricing.py::test_p7_v03_price_change_reflected` | After a price change, the next `GET /api/cart/` shows the new unit price and totals. |
| P7-V04 | API | `api/tests/api/shipping/test_quote.py::test_p7_v04_zones_differ` | CP 06700 (CMX, `local`) and CP 97000 (YUC, `nacional`) return different zones and prices under the §2.5 dev defaults. |
| P7-V05 | API | `api/tests/api/shipping/test_quote.py::test_p7_v05_free_shipping_above_threshold` | A subtotal above the threshold quotes `price_cents: 0`. |
| P7-V06 | unit | `api/tests/unit/orders/test_pricing.py::test_p7_v06_iva_example` | `compute_totals` for 116000 centavos returns `tax_included_cents = 16000`. |
| P7-V07 [R2] | API | `api/tests/api/carts/test_fulfillment.py::test_p7_v07_pickup_zero_shipping` | Switching to pickup zeroes the shipping line. |

**Added negative and edge cases:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P7-V08 | API | `api/tests/api/shipping/test_quote.py::test_p7_v08_threshold_boundary` | Subtotal 149 999 is charged; 150 000 ships free (brackets are half-open `[min, max)`). |
| P7-V09 | API | `api/tests/api/shipping/test_quote.py::test_p7_v09_unknown_postal_code` | An unknown CP returns 400 with a message; the quote is never a silent 0. |
| P7-V10 | API | `api/tests/api/carts/test_lines.py::test_p7_v10_quantity_bounds` | Quantities 0 and 100 are rejected; 99 is accepted. |
| P7-V11 | API | `api/tests/api/carts/test_lines.py::test_p7_v11_inactive_or_archived_variant` | Adding an inactive or archived variant returns 400; an existing line for one is reported `unavailable`. |
| P7-V12 [R2] | API | `api/tests/api/carts/test_merge.py::test_p7_v12_merge_sums_and_clamps` | The same variant in both carts is summed, clamped to `available`, and reported `reduced`. |
| P7-V13 [R2] | API | `api/tests/api/carts/test_fulfillment.py::test_p7_v13_pickup_availability_rule` | Pickup is offered only when every line is available at a pickup point or is a pre-order. |
| P7-V14 [R2] | API | `api/tests/api/carts/test_notices.py::test_p7_v14_mixed_cart_notice` | A cart with both pre-order and in-stock lines returns the Spanish ship-complete notice with the earliest release date. |
| P7-V15 | integration | `api/tests/integration/carts/test_purge.py::test_p7_v15_stale_cart_boundary` | An unconverted cart untouched for exactly 60 days is kept and one untouched for 60 days + 1s is purged; converted carts are never purged. |
| P7-V16 | API | `api/tests/api/carts/test_isolation.py::test_p7_v16_cart_token_isolation` | A line id belonging to another cart returns 404 to update and delete. |
| P7-V17 | property | `api/tests/property/test_totals.py::test_p7_v17_totals_properties` | The R1 totals and IVA properties from §4.6 (the pickup property joins in R2). |

**Added in conversion:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P7-V18 | API | `api/tests/api/carts/test_csrf.py::test_p7_v18_cart_write_requires_csrf` | `POST /api/cart/lines/` without `X-CSRFToken` returns 403. |

**Fixtures and factories introduced** (reused by later phases)

- `CartFactory`, `CartLineFactory`; `cart_client` — a client carrying a `cart_token` cookie
- `dev_defaults` — runs `seed_dev_defaults` (the warehouse location, zones and rates from §2.5)

### Phase 8 — Orders and the state machine

**Deliverable:** an order can be created from a cart, and every Release 1 transition of 8.A is implemented, logged and tested. No payment integration yet — transitions are driven by a test harness, with the two mock provider methods that T1 and T16 need (ADR-0041).

**Release 1 scope:** delivery transitions; invoice data at checkout; purchase limits (G31); the unit-cost snapshot (G33).

#### 8.A The state machine

States are stored in `order.state`. **Every transition goes through one function.** No view, no admin action, no webhook handler may assign `order.state` directly — enforced by `test_no_direct_state_assignment` (§4.6).

| # | From | Event | To | Guard | Side effects | Release |
|---|---|---|---|---|---|---|
| T1 | `draft` | `checkout_submitted` | `pending_payment` | All lines available; fulfillment target complete; totals recomputed | Freeze line prices; assign `number`; `reserve()` all lines; set `payment_deadline_at`; create provider checkout (see ADR-0041) | R1 |
| T2 | `pending_payment` | `payment_approved` | `paid` | Payment amount == `total_cents`; no pre-order lines | `commit_reservations()`; set `paid_at`; queue confirmation email | R1 |
| T3 | `pending_payment` | `payment_approved` | `awaiting_stock` | Payment amount == `total_cents`; **has** pre-order lines | `commit_reservations()`; set `paid_at`; queue confirmation email naming the release date | R2 |
| T4 | `pending_payment` | `payment_rejected` | `pending_payment` | Before deadline | Log event; keep reservations; let the customer retry | R1 |
| T5 | `pending_payment` | `deadline_passed` | `expired` | `payment_deadline_at < now()` | `release_reservations()`; queue "tu pedido expiró" email | R1 |
| T6 | `pending_payment` | `cancelled_by_customer` | `cancelled` | — | `release_reservations()` | R1 |
| T7 | `paid` | `auto` | `preparing` | `fulfillment_method='delivery'` | — | R1 |
| T8 | `paid` | `auto` | `ready_for_pickup` | `fulfillment_method='pickup'` | Set `pickup_deadline_at`; queue "listo para recoger" email | R2 |
| T9 | `awaiting_stock` | `preorder_allocated` | `preparing` / `ready_for_pickup` | **All** pre-order lines allocated | Consume stock; branch on fulfillment method; queue "ya llegó" email | R2 |
| T10 | `preparing` | `shipment_created` | `shipped` | Shipment row exists with tracking | Set `shipped_at`; queue tracking email | R1 |
| T11 | `shipped` | `marked_delivered` | `delivered` | — | Set `delivered_at` on shipment | R1 |
| T12 | `delivered` | `auto_after_7d` | `completed` | — | Set `completed_at` | R1 |
| T13 | `ready_for_pickup` | `customer_collected` | `picked_up` | Staff action in admin | Record collecting staff user | R2 |
| T14 | `picked_up` | `auto_after_1d` | `completed` | — | Set `completed_at` | R2 |
| T15 | `ready_for_pickup` | `pickup_deadline_passed` | `cancelled` | `pickup_deadline_at < now()` (D4) | Return stock via `adjust_stock(reason='return')`; refund; queue email | R2 |
| T16 | `paid` / `awaiting_stock` / `preparing` / `ready_for_pickup` | `cancelled_by_staff` | `cancelled` | Requires `cancel_reason` | Return stock if already committed; refund in full (see ADR-0041) | R1 from `paid` and `preparing`; R2 from `awaiting_stock` and `ready_for_pickup` |
| T17 | `paid` / `preparing` / `shipped` / `delivered` | `refund_issued` | `refunded` | Refund confirmed by provider; payment belongs to the order (G27, ADR-0043) | Set `refunded_cents` on payment to the running total (G46, ADR-0048); flag an issued CFDI for review (T9.14) | R1 |
| T18 | `paid` / `preparing` / `shipped` / `delivered` | `partial_refund_issued` | (unchanged) | Refund confirmed; payment belongs to the order (G27, ADR-0043) | Set `refunded_cents` on payment to the running total (G46, ADR-0048); order keeps its state and stays fulfillable (G26, ADR-0043); flag an issued CFDI for review (T9.14) | R1 |
| T19 | `awaiting_stock` | `cancelled_by_customer` | `cancelled` | Only if D9 permits | Release pre-order allocation; full refund | R2 |

**Terminal states:** `completed`, `cancelled`, `expired`, `refunded`.

**Refunds are payment records (G26, G27, ADR-0043).** `partial_refund_issued` never changes the order state, so the `partially_refunded` state is not entered in Release 1 (it stays in the enum and the schema). From `completed`, `expired` and `cancelled`, both `refund_issued` and `partial_refund_issued` are accepted as recorded payment events: they add an `order_event` row and set the payment's `refunded_cents`, and leave the order in its state. Their guards are those of T17 and T18. From `refunded`, every event is still illegal.

`TRANSITIONS` holds exactly the rows of the release in progress. Anything not in `TRANSITIONS` is illegal and must raise `IllegalTransition(from_state, event)`. In Release 1 an event of an R2 row is illegal like any other. P8-V07 derives its cases from `TRANSITIONS`, so the R2 rows join in Release 2 without editing it.

#### Tasks

- [x] **T8.1 — The state machine** (2026-10-25, 2dcfc62)
  - Release: R1 · Gate: task
  - REQs: REQ-020
  - Verifies: P8-V02, P8-V05, P8-V07, P8-V16
  - Depends on: Phase 7 closed
  - Context: 8.A; §4.6 (Property-based, Architecture)

`apps/orders/state_machine.py`:

```python
TRANSITIONS: dict[tuple[str, str], Transition] = {...}   # the R1 rows of 8.A, verbatim

@transaction.atomic
def apply_event(order_id: int, event: str, *, actor: str = "system", **kwargs) -> Order:
    order = Order.objects.select_for_update().get(pk=order_id)
    t = TRANSITIONS.get((order.state, event))
    if t is None:
        raise IllegalTransition(order.state, event)
    t.guard(order, **kwargs)          # raises on failure
    from_state = order.state
    order.state = t.to_state(order)   # callable: T7/T8 and T9 branch on fulfillment_method
    t.effects(order, **kwargs)
    order.save()
    OrderEvent.objects.create(order=order, from_state=from_state,
                              to_state=order.state, event=event,
                              actor=actor, payload=kwargs)
    return order
```

`select_for_update()` is not optional. Webhooks, cron jobs, and the admin all mutate orders concurrently. A test parses the 8.A table of this spec and asserts that `TRANSITIONS` equals its rows for the release in progress.

- [x] **T8.3 — Order numbers** (2026-10-25, f1eed46)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P8-V12
  - Depends on: T8.1
  - Context: §4.4 (Pending schema changes)

Order number: `CN-{YYYY}-{seq:06d}`, from a Postgres sequence per year. Never derive it from the primary key. Per G5's resolution (ADR-0030), the year is taken in the store timezone (`America/Mexico_City`) and each year's sequence is created on first use.

- [x] **T8.10 — Mock provider: checkout and refund** (2026-10-25, 75313cf)
  - Release: R1 · Gate: task
  - REQs: REQ-032
  - Verifies: P8-V06
  - Depends on: T8.1
  - Context: §4.3; 9.9 (in Phase 9)

Per ADR-0041 (G25), build the two `MockPaymentProvider` methods that Phase 8 needs, ahead of the rest of the mock (9.9):

- `create_checkout(order)` stores a preference in the JSON store under `MOCK_STORE_DIR/payments/` (written atomically: temp file + rename) and returns `SITE_URL/dev/payments/checkout/<preference_id>/`. T1 calls it.
- `refund(payment, amount_cents)` records the refund in the store and returns a `RefundResult`. T16 calls it.

Phase 9 completes the mock (`fetch_payment`, `find_payments`, `verify_webhook`, notifications and the simulator) on top of these.

- [x] **T8.2 — Order creation from the cart** (2026-10-25, eef9a4e)
  - Release: R1 · Gate: task
  - REQs: REQ-010, REQ-020
  - Verifies: P8-V01, P8-V11
  - Depends on: T8.1, T8.3, T8.10
  - Context: 8.A; §4.4; §4.6 (Concurrency)

`apps/orders/services.py::create_order_from_cart(cart, *, email, fulfillment_method, address_or_location, customer=None) -> Order`:

1. Lock every relevant `stock_item` in a deterministic order (sort by `variant_id`) to avoid deadlocks.
2. Re-validate availability line by line. Any failure aborts the whole checkout with a per-line error payload.
3. Freeze prices, names, options and image keys into `order_line`.
4. Compute totals via `compute_totals` (7.9).
5. Snapshot the address into `order.shipping_address` as JSON.
6. Set `has_preorder_items` and `earliest_release_date` (always false and empty in Release 1).
7. Create the order in `draft`, then immediately `apply_event(order, "checkout_submitted")`.

In Release 1 the target is always a delivery address given in the request; a saved address (`customer`) and a pickup location are Release 2. T8.7, T8.8 and T8.9 add their steps to this function.

- [x] **T8.4 — Checkout endpoint** (2026-10-25, 24aa544)
  - Release: R1 · Gate: task
  - REQs: REQ-002, REQ-010, REQ-021
  - Verifies: P8-V03, P8-V08, P8-V10, P8-V18
  - Depends on: T8.2
  - Context: §4.6 (API)

Checkout endpoint `POST /api/checkout/` — R1 body: `{email, phone, fulfillment_method: "delivery", address_payload, customer_note}`, plus the optional `invoice` object (T8.7). `address_id` (a saved address) and `pickup_location_id` are Release 2. Returns `{order_number, order_public_id, checkout_url}`.

Idempotency: accept an `Idempotency-Key` header and return the existing order on replay. A double-clicked "Pagar" button must not create two orders holding two sets of stock. The key is stored on the order with a fingerprint of the request body, unique per cart token (G3, ADR-0030); the same key with a different body returns 422 `idempotency_key_reused`. A price change since the customer's last view is handled by T8.12 (G4, ADR-0042).

- [x] **T8.12 — Checkout expected total** (2026-10-25, 9e56f19)
  - Release: R1 · Gate: task
  - REQs: REQ-002
  - Verifies: P8-V09
  - Depends on: T8.4
  - Context: §4.6 (API); T8.4

Per G4's resolution (ADR-0042), `POST /api/checkout/` takes an optional integer `expected_total_cents`: the total the customer last saw. After `create_order_from_cart` has re-validated the lines and computed the totals (T8.2 steps 2 to 4), and before it creates the order, a total that differs from `expected_total_cents` raises an error and the endpoint returns 409 `{"code": "total_changed", "totals": {subtotal_cents, shipping_cents, discount_cents, total_cents, tax_included_cents}}` with the fresh totals. No order and no reservation is created. Without the field, no comparison is made. An `Idempotency-Key` replay returns the existing order before the comparison. The field is part of the request-body fingerprint (G3). Stock failures keep their own 409 `lines_unavailable` and are checked first.

- [x] **T8.7 — Invoice data at checkout** (2026-10-25, 9218f7c)
  - Release: R1 · Gate: task
  - REQs: REQ-060
  - Verifies: P8-V19
  - Depends on: T8.4
  - Context: §4.4 (CFDI catalog codes); A8
  - Open items: D16 (stand-in §2.5)

Checkout accepts an optional `invoice` object: `{rfc, legal_name, fiscal_postal_code, tax_regime, cfdi_use}` (the D16 stand-in fields, §2.5). The serializer checks:

- `rfc`: uppercase, 3 or 4 letters (including `Ñ` and `&`), 6 digits and 3 alphanumeric characters (`^[A-ZÑ&]{3,4}\d{6}[A-Z\d]{3}$`)
- `fiscal_postal_code`: 5 digits
- `tax_regime` and `cfdi_use`: codes present in `api/fixtures/cfdi_catalogs.json`

`create_order_from_cart` creates the `invoice_request` with status `requested` in the order's transaction. Invalid data returns 400 with field errors and creates no order. Without the object, no request is created. Issuing is manual and happens in the admin (T10.14).

- [x] **T8.8 — Purchase limits per customer** (2026-10-25, 7606cfd)
  - Release: R1 · Gate: task
  - REQs: REQ-061
  - Verifies: P8-V20
  - Depends on: T8.4
  - Context: §4.4 (Pending schema changes)
  - Open items: D15 (stand-in: factory values in tests)

Per G31's resolution (ADR-0030): a variant may carry a per-customer limit (`variant.purchase_limit`), with its time window in days as the setting `PURCHASE_LIMIT_WINDOW_DAYS` (§4.7). Before reserving, `create_order_from_cart` counts that variant's units in `pending_payment` and paid-or-later orders whose email, phone or normalised shipping address matches the new order's within the window. If the new order would exceed the limit, checkout returns 409 with a per-line error and reserves nothing. The limit values and the window length are D15; tests use factory values.

- [x] **T8.9 — Unit-cost snapshot** (2026-10-25, e9c1a7d)
  - Release: R1 · Gate: task
  - REQs: REQ-063
  - Verifies: P8-V21
  - Depends on: T8.2
  - Context: §4.4 (Pending schema changes)

Per G33's resolution (ADR-0030): `create_order_from_cart` snapshots `variant.cost_cents` into `order_line.unit_cost_cents` when it freezes the line (step 3), or `NULL` when the variant has no cost. Later cost changes never alter it. The weekly and monthly reports read it (T10.16).

- [x] **T8.5 — Order admin** (2026-10-25, c0a5998)
  - Release: R1 · Gate: task
  - REQs: REQ-020
  - Verifies: P8-V15
  - Depends on: T8.2
  - Context: 8.A

Admin `OrderAdmin`: read-only lines and totals; a state-transition action bar that calls `apply_event` (buttons rendered only for currently legal events); the `order_event` timeline inline; internal notes. Make `state` non-editable in the form.

- [x] **T8.6a — Order deadlines and auto-completion** (2026-10-26, d1f9361)
  - Release: R1 · Gate: phase-close
  - REQs: REQ-010, REQ-022
  - Verifies: P8-V04, P8-V13, P8-V14
  - Depends on: T8.5, T8.7, T8.8, T8.9, T8.12, T8.13
  - Context: 8.A; §4.8

`manage.py advance_orders` — runs T12 (auto-completion). T5 (payment deadline expiry) is fired by `expire_reservations`, which from this task calls `apply_event` for the order after releasing its holds (G37); add that order-state assertion to the P4-V03 test. Idempotent, safe to run every 5 minutes: add its line to `infra/crontab` (§4.8).

- [x] **T8.13 — Refunds are payment records** (2026-10-25, 7291fff)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: —
  - Depends on: T8.1
  - Context: 8.A (T17, T18, "Refunds are payment records"); ADR-0043

Per G26 and G27 (ADR-0043), change `TRANSITIONS` and its tests to the 8.A table as amended:

- T18 keeps the order's state. `partially_refunded` is no longer a target.
- T17 and T18 are added from `completed`, `expired` and `cancelled`, with the order state unchanged and the same guards and the same `refunded_cents` effect. The CFDI flag stays with T9.14.
- `refunded` still rejects every event.

Tests updated with the spec change (listed in the task report, CR-38): the 8.A table parser of `test_state_machine.py` (unit), P8-V01 `[row]` cases for T17 and T18, P8-V07 (terminal states), and the P8-V05 stateful machine. No new Verify ID, no schema change.

- [ ] **T8.6b — Pickup deadlines and pickup auto-completion**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P8-V23
  - Depends on: T8.11
  - Context: 8.A; §4.8

`advance_orders` also runs T14 (pickup auto-completion) and T15 (pickup deadline expiry).

- [ ] **T8.11 — Release 2 transitions**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P8-V17, P8-V22, P8-V24
  - Depends on: Phase 8 closed; D9 (for T19)
  - Context: 8.A; 10.A
  - Open items: G6 (tests xfail until decided)

Add the R2 rows of 8.A to `TRANSITIONS`: T3, T8, T9, T13, T14, T15, T19, and T16 from `awaiting_stock` and `ready_for_pickup`. Checkout accepts `pickup_location_id` for pickup orders and `address_id` for a customer's saved address; `create_order_from_cart` takes the pickup branch (zero shipping, `pickup_location_id`) and sets `has_preorder_items` and `earliest_release_date`.

Execution order: T8.1, T8.3, T8.10, T8.2, T8.4, T8.12, T8.7, T8.8, T8.9, T8.13, T8.5, T8.6a (phase-close, last of Release 1); then, in R2, T8.11 and T8.6b. IDs keep their numbers (OA-47). T8.13 needs only T8.1. T8.2 needs T8.3 and T8.10 first; T8.7, T8.8 and T8.9 add their steps to `create_order_from_cart` (T8.2); T8.11 needs Phase 8 closed, and T8.6b needs T8.11.

#### Verify — test specification

> Every ID below is a named test (§4.6). The phase closes when every in-scope ID passes in `make test-all` (§0.2). ⚠️ G# marks a test written against a gap's proposed resolution, `xfail(strict=True, reason="G#")` until the gap is decided (§2.4). `[R2]` marks an ID outside Release 1; `[manual]` an ID checked by hand in the phase-close report.

**From the original Verify items:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P8-V01 | integration | `api/tests/integration/orders/test_transitions.py::test_p8_v01_transition_table[row]` | One case per R1 row of 8.A (T1, T2, T4, T5, T6, T7, T10, T11, T12, T16 from `paid` and `preparing`, T17, T18). T17 and T18 also run from `completed`, `expired` and `cancelled`, where the order state stays the same and the payment's `refunded_cents` is set (G27); T18 leaves the state unchanged from every source (G26). From the row's source state: a passing guard yields the target state and the listed side effects; a failing guard raises and leaves the order unchanged. The R2 rows are P8-V22. |
| P8-V02 | unit | `api/tests/unit/orders/test_state_machine.py::test_p8_v02_delivered_on_pending_payment_illegal` | `apply_event(order, "marked_delivered")` on `pending_payment` raises `IllegalTransition`. |
| P8-V03 | API | `api/tests/api/orders/test_checkout.py::test_p8_v03_idempotent_checkout` | The same `Idempotency-Key` twice returns the same order number, with one order and one set of reservations. |
| P8-V04 | concurrency | `api/tests/concurrency/test_order_races.py::test_p8_v04_approve_vs_deadline` | `payment_approved` racing `deadline_passed`: exactly one wins. `paid` → `on_hand` decremented and `reserved` 0; `expired` → `reserved` 0 and `on_hand` unchanged. |
| P8-V05 | property | `api/tests/property/test_state_machine.py::test_p8_v05_one_event_row_per_transition` | In the stateful machine, every legal transition adds exactly one `order_event` with the correct `from_state` / `to_state`, and illegal events add none. |
| P8-V06 | integration | `api/tests/integration/orders/test_cancel.py::test_p8_v06_cancel_paid_returns_stock` | T16 on a `paid` order restores `on_hand`, writes a `return` ledger row, and calls `provider.refund`. |

**Added negative and edge cases:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P8-V07 | integration | `api/tests/integration/orders/test_transitions.py::test_p8_v07_every_illegal_event_rejected[state-event]` | Every one of the 14 states × every event absent from `TRANSITIONS` for that state raises `IllegalTransition`; the order row, its reservations and `order_event` are untouched. Terminal states reject every event, except the two refund events from `completed`, `expired` and `cancelled` (G27); `refunded` rejects every event. |
| P8-V08 | API | `api/tests/api/orders/test_checkout.py::test_p8_v08_idempotency_key_reused_different_body` | The same key with a different body — proposed: 422 `idempotency_key_reused`, no new order, the original untouched. |
| P8-V09 | API | `api/tests/api/orders/test_checkout.py::test_p8_v09_price_change_between_cart_and_checkout` | The price rises after the last cart GET: `order_line.unit_price_cents` is the checkout-time price, and later price changes do not alter the order. A checkout sent with the previously seen `expected_total_cents` returns 409 `total_changed` with the fresh totals, creates no order and reserves nothing (G4, ADR-0042). |
| P8-V10 | API | `api/tests/api/orders/test_checkout.py::test_p8_v10_partial_stock_failure_atomic` | One short line returns 409 with per-line errors; no order and no reservations are created. |
| P8-V11 | concurrency | `api/tests/concurrency/test_order_races.py::test_p8_v11_crossed_carts_no_deadlock` | Carts `[A, B]` and `[B, A]` check out concurrently and both finish within the timeout — each succeeds or fails with `InsufficientStock` — thanks to the sorted locking in 8.2. |
| P8-V12 | unit | `api/tests/unit/orders/test_numbering.py::test_p8_v12_number_format_and_year_rollover` | Format `CN-YYYY-NNNNNN`; the sequence restarts each year; an order at 23:59 on 31 December local time gets the year from G5. |
| P8-V13 | integration | `api/tests/integration/orders/test_advance.py::test_p8_v13_auto_completion_boundaries` | `delivered` completes at exactly 7 days and not at 7 days − 1s. *The `picked_up` case is P8-V23.* |
| P8-V14 | integration | `api/tests/integration/orders/test_advance.py::test_p8_v14_advance_orders_idempotent` | Running `advance_orders` twice produces the same states and no duplicate events. |
| P8-V15 | integration | `api/tests/integration/orders/test_admin.py::test_p8_v15_action_bar_legal_events_only` | The buttons rendered equal the legal events for the state; POSTing an illegal event shows an error and changes nothing. |
| P8-V16 | integration | `api/tests/integration/orders/test_cancel.py::test_p8_v16_staff_cancel_requires_reason` | T16 without `cancel_reason` is rejected. |
| P8-V17 [R2] | integration | `api/tests/integration/orders/test_cancel.py::test_p8_v17_cancel_awaiting_stock_releases_preorder` | Cancelling an `awaiting_stock` order — proposed: `preorder_committed` drops by the order's quantity. ⚠️ G6 |
| P8-V18 | API | `api/tests/api/orders/test_checkout.py::test_p8_v18_checkout_validation` | A missing email, delivery without an address, or an empty cart returns 400 with field errors and reserves nothing. *Pickup without a location is P8-V24.* |

**Added in conversion:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P8-V19 | API | `api/tests/api/orders/test_checkout_invoice.py::test_p8_v19_invoice_data_at_checkout` | Checkout accepts optional invoice data. Valid data creates one `requested` `invoice_request` in the order's transaction. An RFC in the wrong format, a 4-digit fiscal postal code, or a régimen or uso code outside the configured catalog returns 400 with field errors and creates no order. Without invoice data, no request is created. |
| P8-V20 | API | `api/tests/api/orders/test_purchase_limits.py::test_p8_v20_purchase_limit_per_customer` | With a limit of N units per customer on a variant, a checkout that would bring that variant's units in paid or pending orders matching the same email, phone or shipping address within the window above N returns 409 with a per-line message and reserves nothing. Exactly N is accepted. |
| P8-V21 | integration | `api/tests/integration/orders/test_cost_snapshot.py::test_p8_v21_unit_cost_snapshot` | `order_line` stores the variant's unit cost when the order is created; a later cost change doesn't alter it; a variant with no cost stores `NULL`. |
| P8-V22 [R2] | integration | `api/tests/integration/orders/test_transitions.py::test_p8_v22_transition_table_r2[row]` | One case per R2 row of 8.A (T3, T8, T9, T13, T14, T15, T19, and T16 from `awaiting_stock` and `ready_for_pickup`). From the row's source state: a passing guard yields the target state and the listed side effects; a failing guard raises and leaves the order unchanged. |
| P8-V23 [R2] | integration | `api/tests/integration/orders/test_advance.py::test_p8_v23_pickup_auto_completion_boundary` | `picked_up` completes at exactly 1 day and not before. |
| P8-V24 [R2] | API | `api/tests/api/orders/test_checkout.py::test_p8_v24_pickup_checkout_validation` | A pickup checkout without a location returns 400 with field errors and reserves nothing. |

**Fixtures and factories introduced** (reused by later phases)

- `order_in_state(state, fulfillment="delivery", preorder=False)` — reaches the state **only** through a real checkout plus `apply_event`, so fixtures cannot build impossible orders. `OrderFactory` state traits delegate to it. Pickup and pre-order traits arrive in Release 2
- `checkout(client, cart, **body)` — posts to `/api/checkout/` and returns the response
- `transition_table` — the `TRANSITIONS` mapping exposed for parametrisation (the R1 rows in Release 1)
- `OrderStateMachine` — the hypothesis stateful machine

### Phase 9 — Payments (mocked)

**Deliverable:** the complete payment pipeline — checkout, webhooks, status mapping, deadlines, reconciliation, refunds — running against `MockPaymentProvider` with no network access. A tester can drive every outcome from a local simulator page, and the provider-agnostic payment contract suite (9.13) passes. Everything downstream of the adapter is exactly the code production runs; Phase 16 swaps only the adapter.

**Release 1 scope:** all tasks, plus the CFDI review flag on refunds (T9.14).

#### 9.A Ground rules

1. **The webhook is authoritative. The browser redirect is not.** A customer who closes the tab after paying must still get their order. A customer who edits the return URL must not.
2. **Never trust webhook payload amounts.** A notification carries only IDs. Fetch the payment with `fetch_payment()` and read the amount and status from that response. The mock enforces this: its notification bodies contain no amount and no status.
3. **Verify the signature** with the active provider's webhook secret before doing anything. Reject timestamps older than `WEBHOOK_MAX_AGE_SECONDS` (default 300). Log and reject failures; alert if more than a handful occur in an hour.
4. **Idempotency comes from the database.** `webhook_event` has `UNIQUE (provider, topic, external_id)`, and **`external_id` is the provider's notification (delivery) id, not the payment id.** One payment legitimately produces several notifications — an OXXO payment goes `pending`, then `approved` — so keying on the payment id would silently drop the approval. Duplicate deliveries of one notification share its id. Insert first; an `IntegrityError` means "already seen" → return 200 and stop.
5. **Acknowledge fast.** Commit the `webhook_event` row, try to process it inline within `WEBHOOK_INLINE_BUDGET_MS`, and return 200 either way. Anything that fails processing stays unprocessed for `process_webhooks` (§4.8) to retry.
6. **Process state, not events.** Every notification triggers a fresh `fetch_payment()`. The order moves only if the fetched status implies a legal transition from its current state, so seeing the same status twice is a no-op.

These are CR-11 to CR-16.

#### 9.B How the pieces fit

```text
checkout (8.4) ─► payment_provider().create_checkout(order) ─► CheckoutSession.url
                                                                  │
     Part A: /dev/payments/checkout/<id>/ (simulator, 9.10)       │   Part B: Mercado Pago Checkout Pro
                                                                  ▼
                        provider records outcome ─► notification (ids only, HMAC-signed)
                                                                  │
     POST /api/webhooks/payments/<provider>/ (9.3) ◄──────────────┘
        verify_webhook → insert webhook_event → fetch_payment → mapping (9.4) → apply_event
                                                                  ▲
     reconcile_payments (9.7) ── find_payments(order.public_id) ──┘   safety net for dropped webhooks
```

Everything on the application side of the adapter is shared. In Part A, the provider side is `apps/payments/mock.py` plus the simulator; in Part B it is Mercado Pago.

#### Tasks

Execution order: T9.1, T9.2, T9.9, T9.3, T9.4, T9.5, T9.6, T9.15, T9.7, T9.8, T9.14, T9.16, T9.10, T9.11, T9.12a, T9.12b, T9.13a, T9.17, T9.13b (phase-close, last). IDs keep their numbers (OA-52). T9.9 comes before T9.3 because the endpoint verifies and fetches through the mock. T9.15 follows T9.6 and adds the provider method that a late voucher needs (OA-55). T9.14 follows T9.8 because it extends the refund side effects. T9.16 changes checkout (T8.4) and depends only on it; it runs before the simulator so the payment flow is exercised with the final cart behaviour (OA-58). T9.10 to T9.12b are dev tooling and need T9.9, T9.3 and T9.7. Mentions of a later task inside an earlier one (T9.3 "the mapping in 9.4", T9.4 "extend deadline (9.5)" and the refund events T17/T18) are not dependencies: T9.3 leaves the mapping step as a stub that T9.4 fills, and the T9.8/T9.14 side effects are added when those tasks run.

- [x] **T9.1 — Payment interface and value types** (2026-10-26, 8e38eb7)
  - Release: R1 · Gate: task
  - REQs: REQ-030
  - Verifies: [no-test: value types and the Protocol; exercised from T9.2 on, and checked by the adapter test in T9.9]
  - Depends on: Phase 8 closed
  - Context: §4.3

`apps/payments/base.py` — the interface and its value types:

```python
class NormalizedStatus(StrEnum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    CHARGED_BACK = "charged_back"

@dataclass(frozen=True)
class ProviderPayment:
    provider_payment_id: str
    external_reference: str            # order.public_id
    status: NormalizedStatus
    status_detail: str                 # provider's raw detail, for logs and the admin
    method: str                        # 'credit_card','debit_card','oxxo','spei','wallet'
    amount_cents: int
    refunded_cents: int
    installments: int | None
    voucher_url: str | None
    voucher_expires_at: datetime | None
    raw: Mapping[str, Any]

@dataclass(frozen=True)
class WebhookRef:
    topic: str                         # 'payment'
    notification_id: str               # -> webhook_event.external_id
    resource_id: str                   # provider payment id

class PaymentNotFound(Exception): ...
class RefundNotSupported(Exception): ...

class PaymentProvider(Protocol):
    code: str                          # 'mock' | 'mercadopago'; also the webhook path segment
    def create_checkout(self, order: Order) -> CheckoutSession: ...
    def fetch_payment(self, provider_payment_id: str) -> ProviderPayment: ...
    def find_payments(self, external_reference: str) -> list[ProviderPayment]: ...
    def refund(self, payment: Payment, amount_cents: int | None) -> RefundResult: ...
    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> WebhookRef | None: ...
    def cancel_payment(self, provider_payment_id: str) -> None: ...  # T9.15, OA-55
```

`find_payments` exists because reconciliation (9.7) must look payments up by order, and nothing else in the interface can. Each adapter maps its provider's vocabulary into `NormalizedStatus`; everything after that point is shared.

`apps/payments/mock.py` implements it for Part A (`PAYMENT_PROVIDER=mock`); `apps/payments/mercadopago.py` implements it in Phase 16. Callers obtain it only via `providers.payment_provider()`. **Nothing outside `mercadopago.py` imports the Mercado Pago SDK** — enforced by `tests/architecture/test_vendor_imports.py` (§4.3).

- [x] **T9.2 — Money conversion and signing helpers** (2026-10-26, 8ed458e)
  - Release: R1 · Gate: task
  - REQs: REQ-001, REQ-030
  - Verifies: P9-V08, P9-V20
  - Depends on: T9.1
  - Context: §4.6 (Property-based)

Shared helpers, used by every adapter and unit-tested once:

- `apps/payments/money.py` — `cents_to_pesos(int) -> Decimal` and `pesos_to_cents(Decimal | str) -> int`. This is the only conversion point between the database's centavos and a provider's pesos. It rejects sub-centavo values instead of rounding them.
- `apps/payments/signing.py` — `sign(secret, *, resource_id, request_id, ts) -> str` and `verify(secret, headers, resource_id, *, max_age) -> bool`: HMAC-SHA256 with a constant-time comparison. Header shape is `x-signature: ts=<unix>,v1=<hex>` plus `x-request-id`, modelled on Mercado Pago's documented scheme. Phase 16 confirms the exact signed manifest against current Mercado Pago documentation.

- [x] **T9.9 — The mock payment provider** (2026-10-26, 0cd898e)
  - Release: R1 · Gate: task
  - REQs: REQ-040
  - Verifies: P9-V06, P9-V18
  - Depends on: T9.2, T8.10
  - Context: §4.3; 9.A

`MockPaymentProvider` — `apps/payments/mock.py`, `code = "mock"`. T8.10 built `create_checkout` and `refund`; this task completes it.

- **Storage.** State lives in a JSON file store under `MOCK_STORE_DIR/payments/` (default `var/mocks/payments/`), one file per preference, payment and queued notification, each written atomically (temp file + rename). It is deliberately **not** in the application database: a real provider's state is outside our transactions, and a mock that shared them would hide exactly the bugs reconciliation exists to catch. Tests point `MOCK_STORE_DIR` at `tmp_path`.
- **`create_checkout`** stores a preference (lines, total in pesos via `cents_to_pesos`, `external_reference`, `back_urls`, expiry = `order.payment_deadline_at`) and returns `SITE_URL/dev/payments/checkout/<preference_id>/`.
- **`fetch_payment` / `find_payments`** read the store and build `ProviderPayment` through `pesos_to_cents`, so the conversion path matches production. An unknown id raises `PaymentNotFound`, as the real adapter will.
- **`verify_webhook`** uses `signing.verify` with `MOCK_PAYMENT_WEBHOOK_SECRET`.
- **`refund`** appends to the stored payment's refunds, updates its status, queues a notification, and raises `RefundNotSupported` for `oxxo`.
- **Ids** are prefixed `mock_pref_…`, `mock_pay_…`, `mock_ntf_…`, so a mock id can never be mistaken for a real one in logs or data.

- [x] **T9.3 — Webhook endpoint and processing** (2026-10-26, 0e5a3a6)
  - Release: R1 · Gate: task
  - REQs: REQ-030, REQ-031
  - Verifies: P9-V10, P9-V11, P9-V12, P9-V13, P9-V17
  - Depends on: T9.9
  - Context: 9.A, 9.B; §4.8

Webhook endpoint `POST /api/webhooks/payments/<provider>/` — CSRF-exempt, unauthenticated, rate-limited, and **excluded from the CDN**. `<provider>` must equal `payment_provider().code`; any other value is 404. Part A receives at `/api/webhooks/payments/mock/`, Phase 16 at `/api/webhooks/payments/mercadopago/`.

```text
handle(request):
  1. ref = provider.verify_webhook(headers, raw_body)
       None  -> store webhook_event(signature_ok=false), return 401
  2. INSERT webhook_event(provider, topic, external_id=ref.notification_id, headers, payload)
       IntegrityError -> return 200                      # already seen
  3. try process_webhook_event(id) within WEBHOOK_INLINE_BUDGET_MS
       any failure -> leave unprocessed for process_webhooks
  4. return 200

process_webhook_event(id):
  payment = provider.fetch_payment(ref.resource_id)
  order   = Order by public_id = payment.external_reference
              missing -> record error, alert, mark processed, stop
  upsert Payment row keyed on (provider, provider_payment_id)
  apply the mapping in 9.4
  set processed_at
```

Also build `manage.py process_webhooks`, which retries unprocessed rows and increments `attempts`; a row is retried up to 10 attempts with exponential backoff, then marked failed and alerted (G7, ADR-0044). Add its line to `infra/crontab` (every minute, §4.8). A timestamp is accepted when `abs(now − ts) ≤ WEBHOOK_MAX_AGE_SECONDS`, so a future timestamp beyond that is rejected as well (G8, ADR-0044).

- [x] **T9.4 — Status mapping** (2026-10-26, 0947204)
  - Release: R1 · Gate: task
  - REQs: REQ-030
  - Verifies: P9-V07
  - Depends on: T9.3
  - Context: 9.A; 8.A

Status mapping — shared by every provider, keyed on `NormalizedStatus`:

| `NormalizedStatus` | `payment.status` | Order event |
|---|---|---|
| `approved` | `approved` | `payment_approved` (T2 / T3) |
| `pending` | `pending` | none — record voucher, extend deadline (9.5), stay `pending_payment` |
| `in_review` | `pending` | none — under review |
| `rejected` | `rejected` | `payment_rejected` (T4) |
| `cancelled` | `cancelled` | none — the expiry job handles it (T5) |
| `refunded` | `refunded` | `refund_issued` (T17) |
| `partially_refunded` | `partially_refunded` | `partial_refund_issued` (T18) |
| `charged_back` | `charged_back` | none — alert a human |

In Release 1 orders have no pre-order lines, so `approved` always fires T2; T3 joins with pre-orders in Release 2.

Rules applied in this order before any `apply_event`:

1. **Amount guard.** For `approved`, require `payment.amount_cents == order.total_cents`. On mismatch, record the payment, refuse the transition, log loudly, and alert. This is the one place where a bug becomes a financial loss.
2. **Already applied.** If the order already reflects this status (for example `approved` for an order that is `paid` or later), record `order_event(event='webhook_no_op')` and stop. This is what makes an admin-initiated refund (9.8) and the refund notification that follows it converge on a single transition.
3. **Late payment.** If the payment is `approved` but the order is `expired` or `cancelled`, record the payment, leave the order in place, and alert. Its stock has already been released, so a human chooses between refunding (9.8) and fulfilling manually. The state machine gains no new transition.
4. Otherwise `apply_event(order, event, actor="webhook")`.

- [x] **T9.5 — Deadlines by payment method** (2026-10-26, d91162d)
  - Release: R1 · Gate: task
  - REQs: REQ-012
  - Verifies: P9-V09
  - Depends on: T9.4
  - Context: §2.5; §4.7
  - Open items: D6 (stand-in §2.5)

Deadlines by method, set when the payment is first observed:

| Method | Reservation TTL | `payment_deadline_at` |
|---|---|---|
| Card, wallet, Mercado Crédito | 30 minutes | now + 30 min |
| SPEI | 4 hours | now + 4 h |
| OXXO cash | voucher expiry + 2 h grace (D6; Part A dev default 72 h, §2.5) | same |

When a `pending` OXXO or SPEI payment arrives, **extend** the existing reservations' `expires_at` and the order's `payment_deadline_at` rather than creating new reservations. In Part A the mock issues vouchers expiring `RESERVATION_TTL_OXXO_HOURS` (SPEI: `RESERVATION_TTL_SPEI_HOURS`) after creation, mirroring the preference expiry the real adapter requests in 16.2. A customer who generates a voucher after the checkout TTL has lapsed follows ADR-0046 (T9.15).

G48: a reservation must never expire before its order's `payment_deadline_at`; extend both together, in one transaction. `expire_reservations` logs a `GuardFailed` from T5 as a one-line warning, not an exception. Add a test with a method whose deadline is longer than the card window.

- [x] **T9.6 — Voucher on the order** (2026-10-26, 68ac58c)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P9-V19
  - Depends on: T9.5
  - Context: 9.4

Store `voucher_url` and `voucher_expires_at` on the payment and surface them on the order status (the serializer behind the guest lookup, T6.7b, and the landing pages, Phase 13) and in the confirmation email. A customer who loses the OXXO ficha and cannot find it will not pay. In Part A the voucher URL points at the mock voucher page (9.10).

- [x] **T9.15 — Cancel a late voucher** (2026-10-26, 3a41873)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P9-V21
  - Depends on: T9.5
  - Context: 9.1, 9.4, 9.5; ADR-0046

Add `cancel_payment(provider_payment_id)` to `PaymentProvider` and to the mock: it ends the stored payment as `cancelled`, and cancelling a payment that is already `cancelled` does nothing. In `mapping.py`, the branch for a `pending` OXXO or SPEI payment on an `expired` or `cancelled` order (T9.5) keeps its alert and the order as it is, and also calls `cancel_payment`. If the provider call fails, the failure is raised like any webhook failure, so the row is retried (G7). The real adapter implements the method in T16.3.

- [x] **T9.7 — Payment reconciliation** (2026-10-26, 93296f4)
  - Release: R1 · Gate: task
  - REQs: REQ-022, REQ-031
  - Verifies: P9-V14
  - Depends on: T9.4
  - Context: 9.A; §4.8

`manage.py reconcile_payments` — for every order in `pending_payment` older than 15 minutes, call `find_payments(order.public_id)` and pass each result through the same processing path as a webhook (upsert the payment row, then apply the 9.4 mapping). This is the safety net for dropped webhooks. Run it every 10 minutes: add its line to `infra/crontab` (§4.8). **Do not skip it.** Webhooks are lost in production; this is what makes the system self-healing. A webhook and reconciliation processing the same approval concurrently treat the second as `webhook_no_op` when the order already reflects the status (G14, ADR-0047).

- [x] **T9.8 — Refunds** (2026-10-26, a86a299)
  - Release: R1 · Gate: task
  - REQs: REQ-032
  - Verifies: P9-V15, P9-V16
  - Depends on: T9.4
  - Context: 8.A (T17, T18)

Refunds — an admin action on `OrderAdmin`, always initiated by a human:

- Reject any amount above the remaining refundable balance before calling the provider (the `payment_refund_le_amount` constraint is the backstop).
- Call `provider.refund(payment, amount_cents)`, update `payment.refunded_cents`, and apply `refund_issued` or `partial_refund_issued`.
- If the provider raises `RefundNotSupported` (OXXO cash), show: *"Los pagos en efectivo (OXXO) no se pueden reembolsar a través del proveedor. Reembolsa por SPEI y registra el reembolso manual."* Then offer **"Registrar reembolso manual"**: it records the amount on the payment with a required note and applies the same event with `actor="staff:<id>"`, without calling the provider.

- [x] **T9.14 — CFDI review flag on refunds** (2026-10-26, c81b264)
  - Release: R1 · Gate: task
  - REQs: REQ-060
  - Verifies: P9-V22
  - Depends on: T9.8
  - Context: §4.4 (`invoice_request`); A12

Add to the side effects of T17 and T18 (8.A): when the order's `invoice_request` is `issued`, set `needs_review = true` and write a `review_note` naming the refund amount, in the same transaction. The admin CFDI queue (T10.14) lists it. The fiscal treatment is the accountant's (D16); the store decides nothing about it. A refund of an order with no issued CFDI changes no request.

- [x] **T9.16 — Cart converted at checkout** (2026-10-26, aab3206)
  - Release: R1 · Gate: task
  - REQs: REQ-021
  - Verifies: P9-V23
  - Depends on: T8.4
  - Context: 8.A (T1); §4.4 (`cart`); ADR-0049

Set `cart.converted_order` to the new order in the same transaction as T1, so a failed checkout leaves the cart open (OA-58, ADR-0049). The consequences, each tested:

- A second checkout from that cart, with a new `Idempotency-Key`, creates no order and no reservation.
- A repeat with the same key and body still returns the original order. The idempotency lookup finds the order by the cart token and the key, whether or not the cart is converted, so the double-click replay keeps working.
- The cart endpoints treat a converted cart as gone: the next add creates a fresh cart, and `purge_stale_carts` still keeps a converted one.

- [x] **T9.10 — Payment simulator pages** (2026-10-26, 356033b)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: [no-test: T9.11's simulator test drives every button once notification delivery exists]
  - Depends on: T9.9
  - Context: §4.3; §4.7 (`DEV_TOOLS_ENABLED`)
  - Open items: D7 (stand-in §2.5)

Simulator pages — Django templates in `apps/payments/devtools/`, routed under `/dev/payments/` only when `DEV_TOOLS_ENABLED` is true. It is true in dev and test settings; `prod.py` forces it false, so in production the routes are not registered and return 404. Caddy forwards `/dev/*` to Django (T1.7). Every page carries a permanent banner: **"SIMULADOR — ningún pago es real"**.

`/dev/payments/checkout/<preference_id>/` shows the order number, lines and total, and one button per outcome:

| Button | Mock payment recorded | Notification queued | Browser redirected to |
|---|---|---|---|
| Aprobar con tarjeta | `approved`, `credit_card` | yes | `back_urls.success` |
| Aprobar a meses sin intereses | `approved`, `credit_card`, installments chosen from `PAYMENT_INSTALLMENT_OPTIONS` | yes | `back_urls.success` |
| Pagar en OXXO | `pending`, `oxxo`, voucher URL + expiry | yes | `back_urls.pending` |
| Pagar por SPEI | `pending`, `spei`, fake CLABE + expiry | yes | `back_urls.pending` |
| Rechazar | `rejected` | yes | `back_urls.failure` |
| Dejar expirar | nothing | no | `back_urls.failure` |

`/dev/payments/voucher/<payment_id>/` renders the fake OXXO ficha or SPEI instructions, with **"Simular pago recibido"** (→ `approved`) and **"Simular vencimiento"** (→ `cancelled`); both queue a notification.

- [x] **T9.11 — Mock notification delivery** (2026-10-26, 1598aac)
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P9-V02
  - Depends on: T9.10, T9.3
  - Context: 9.A; §4.1

Mock notification delivery. The simulator never calls the webhook inline. It appends a notification containing only ids — `{"id": "mock_ntf_…", "type": "payment", "data": {"id": "mock_pay_…"}}` — to the queue in the mock store. `manage.py mock_payments deliver --loop` signs each notification at send time and POSTs it over HTTP through Caddy to `/api/webhooks/payments/mock/`, the same network path production traffic takes, after `MOCK_WEBHOOK_DELAY_SECONDS` (default 2). Add it to `docker-compose.yml` as a `mock-webhooks` service. Tests use `deliver --once` or an in-process transport through the Django test client.

- [x] **T9.12a — Mock payment commands** (2026-10-26, 737e788)
  - Release: R1 · Gate: task
  - REQs: REQ-031
  - Verifies: P9-V04
  - Depends on: T9.11, T9.7
  - Context: §4.7 (`DEV_TOOLS_ENABLED`)

Dev tooling. Every command refuses to run unless `DEV_TOOLS_ENABLED`.

| Command | Purpose |
|---|---|
| `mock_payments approve <order> [--installments N] [--amount-cents X]` | Same as the button. `--amount-cents` records a mismatched amount to exercise the amount guard |
| `mock_payments reject <order>` | Same as the button |
| `mock_payments pay-voucher <payment>` / `expire-voucher <payment>` | Complete or lapse an OXXO/SPEI payment |
| `mock_payments drop <order> --outcome approve\|reject\|pending` | Record the outcome in the mock store **without** queueing a notification. Only `reconcile_payments` can then discover it |
| `mock_payments chargeback <payment>` | Exercise the chargeback alert path |
| `mock_payments expire-order <order>` | Dev clock shortcut: move the order's `payment_deadline_at` and its reservations' `expires_at` into the past, then run `expire_reservations` |
| `mock_payments deliver [--once\|--loop]` | Drain the notification queue (9.11) |
| `mock_payments list [--order N]` / `reset` | Inspect or clear the mock store |

- [x] **T9.12b — Webhook replay commands** (2026-10-26, eb40d17)
  - Release: R1 · Gate: task
  - REQs: REQ-030, REQ-040
  - Verifies: P9-V03, P9-V05
  - Depends on: T9.12a
  - Context: 9.A; §4.7 (`DEV_TOOLS_ENABLED`)

Dev tooling. Every command refuses to run unless `DEV_TOOLS_ENABLED`.

| Command | Purpose |
|---|---|
| `webhooks replay <webhook_event id>` | Re-send a stored notification with the same notification id, freshly signed. Must be a no-op |
| `webhooks duplicate <webhook_event id> --count N [--concurrent]` | N simultaneous deliveries of one notification. Exactly one is processed |
| `webhooks tamper <webhook_event id>` | Re-send with a corrupted signature. Expect 401 and `signature_ok = false` |
| `webhooks stale <webhook_event id>` | Re-send signed with a timestamp older than `WEBHOOK_MAX_AGE_SECONDS`. Expect 401 |

The `webhooks …` commands are provider-agnostic. They rebuild the request from the stored `webhook_event` row and re-sign it with the active provider's secret, so Phase 16 uses them unchanged on captured Mercado Pago notifications.

- [x] **T9.13a — Payment contract suite: driver and core scenarios** (2026-10-26, ff09bfa)
  - Release: R1 · Gate: task
  - REQs: REQ-030, REQ-041
  - Verifies: [no-test: writes PAY-01 to PAY-08, which run under P9-V01; T9.13b owns that ID]
  - Depends on: T9.12b, T9.6
  - Context: 9.A, 9.B; §4.6 (Contract — providers)

Payment contract suite — `tests/contract/payments/`. Scenarios are written once, against a driver:

```python
class PaymentDriver(Protocol):
    name: str
    def supports(self, scenario: str) -> bool | str: ...    # True, or why it can't be driven
    def checkout(self, order: Order) -> CheckoutSession: ...
    def complete(self, session: CheckoutSession, outcome: Outcome, **opts) -> str: ...  # payment id
    def deliver_pending_notifications(self) -> None: ...
```

`MockDriver` (Part A) drives the mock store directly. `MercadoPagoSandboxDriver` arrives in Phase 16. Every scenario goes through the real webhook endpoint, real `webhook_event` rows, and the real state machine; only the driver differs. This task writes PAY-01 to PAY-08; T9.13b writes PAY-09 to PAY-19.

| ID | Scenario | Expected |
|---|---|---|
| PAY-01 | Card approved | `paid`; stock committed; ledger `sale_online`; confirmation email queued |
| PAY-02 | Approved with installments | As PAY-01; `payment.installments` recorded |
| PAY-03 | OXXO pending | Voucher stored and shown; reservations extended to voucher expiry + grace; `expire_reservations` does not release them early |
| PAY-04 | OXXO pending → paid | `pending` then `approved` notifications for one payment; both processed; order `paid` |
| PAY-05 | OXXO voucher expires | Order `expired`; reservations released |
| PAY-06 | SPEI pending → paid | As PAY-04 with SPEI deadlines |
| PAY-07 | Rejected | Order stays `pending_payment`; retry possible before the deadline |
| PAY-08 | Let expire, no payment | Order `expired`; reservations released |
| PAY-09 | Same notification ×5, concurrent | One `payment` row; one transition |
| PAY-10 | Replay a processed notification | No-op |
| PAY-11 | Tampered signature | 401; `signature_ok = false`; nothing processed |
| PAY-12 | Stale timestamp | 401 |
| PAY-13 | Amount mismatch | Payment recorded; no transition; alert raised |
| PAY-14 | Dropped notification | `reconcile_payments` reaches `paid`; the late delivery afterwards is `webhook_no_op` |
| PAY-15 | Payment approved after the order expired | Payment recorded `approved`; order stays `expired`; alert raised |
| PAY-16 | Full refund / partial refund / over-refund | `refunded` / `partially_refunded` / rejected before calling the provider |
| PAY-17 | OXXO refund | `RefundNotSupported`; admin warning; manual refund recorded; order `refunded` |
| PAY-18 | Chargeback | Alert; no transition |
| PAY-19 | Notification for an unknown order | Stored; marked processed with an error; alert; no crash |

- [x] **T9.17 — Close Phase 9 coverage gaps** (2026-10-26, 56b0b72)
  - Release: R1 · Gate: task
  - REQs: REQ-030, REQ-041
  - Verifies: [no-test: adds tests for uncovered branches in apps/payments and apps/inventory; no new Verify ID]
  - Depends on: T9.12b
  - Context: §0.3 (coverage ratchet); 9.A

Add tests for the uncovered branches in `webhooks.py`, `mapping.py`, `mock.py`, `devtools/delivery.py`, `devtools/replay.py`, `devtools/views.py`, `mock_payments.py`, the `webhooks` command and `expire_reservations.py`, until `make test-all` passes the coverage ratchet without lowering the baseline. Change no production code.

- [ ] **T9.13b — Payment contract suite: idempotency, security and recovery**
  - Release: R1 · Gate: phase-close
  - REQs: REQ-030, REQ-041
  - Verifies: P9-V01, PAY-09 to PAY-19
  - Depends on: T9.13a, T9.7, T9.8, T9.14, T9.17
  - Context: the 9.13 scenario table in T9.13a; 9.A

Write PAY-09 to PAY-19 from the table in T9.13a against the same `PaymentDriver`, and the completeness check P9-V01.

#### Verify — test specification

> Every ID below is a named test (§4.6). The phase closes when every in-scope ID passes in `make test-all` (§0.2). ⚠️ G# marks a test written against a gap's proposed resolution, `xfail(strict=True, reason="G#")` until the gap is decided (§2.4). `[R2]` marks an ID outside Release 1; `[manual]` an ID checked by hand in the phase-close report.

**From the original Verify items:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P9-V01 | contract | `api/tests/contract/payments/test_suite_complete.py::test_p9_v01_all_scenarios_present_and_supported` · runs with `test_scenarios.py::test_pay_01_…` to `test_pay_19_…` | Every scenario ID PAY-01 to PAY-19 in 9.13 has a test in `test_scenarios.py`; `MockDriver.supports()` is `True` for all of them; the scenarios themselves pass with sockets disabled. |
| P9-V02 | integration | `api/tests/integration/payments/test_simulator.py::test_p9_v02_each_button_outcome[button]` | The Django test client submits each of the six checkout buttons and both voucher buttons, then `deliver --once`. Each yields the expected order state, payment row, `order_event` timeline and redirect target. |
| P9-V03 | integration | `api/tests/integration/payments/test_devtools.py::test_p9_v03_devtools_absent_in_prod` | Under `prod.py`: `/dev/payments/…` returns 404; `mock_payments list` and every `webhooks …` command raise `CommandError`. |
| P9-V04 | integration | `api/tests/integration/payments/test_reconcile.py::test_p9_v04_dropped_reconciled_then_late_delivery` | `drop` → `reconcile_payments` → `paid`; a later `deliver` records `webhook_no_op` and no second transition. |
| P9-V05 | concurrency | `api/tests/concurrency/test_webhooks.py::test_p9_v05_duplicate_command_concurrent` | `webhooks duplicate --count 5 --concurrent`: one processed row, one transition, four 200 short-circuits. |
| P9-V06 | architecture | `api/tests/architecture/test_vendor_imports.py::test_p9_v06_payment_adapters_clean` | `apps/payments/mock.py` imports no allowlisted vendor package, and every `PAYMENT_IMPLS` entry resolves. |

**Added negative and edge cases:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P9-V07 | integration | `api/tests/integration/payments/test_mapping.py::test_p9_v07_amount_off_by_one_centavo[+1,-1]` | `amount_cents = total ± 1`: the payment is recorded `approved`, the order stays `pending_payment`, and an alert is captured. |
| P9-V08 | unit | `api/tests/unit/payments/test_money.py::test_p9_v08_conversion_edges` | `"1160.00" → 116000`; `"1160.009"` and negative amounts are rejected; the round-trip property from §4.6 holds. |
| P9-V09 | integration | `api/tests/integration/payments/test_deadlines.py::test_p9_v09_ttl_boundaries[card,spei,oxxo]` | Card: not expired at checkout + 30 min, expired at + 30 min + 1µs. SPEI extends to 4 h from `pending`; OXXO to voucher expiry + 2 h. Extension creates no new reservations. |
| P9-V10 | integration | `api/tests/integration/payments/test_webhook.py::test_p9_v10_timestamp_age_boundary` | A signature aged exactly `WEBHOOK_MAX_AGE_SECONDS` is accepted; one second older returns 401. A timestamp in the future by more than `WEBHOOK_MAX_AGE_SECONDS` returns 401 too (G8, ADR-0044). |
| P9-V11 | API | `api/tests/api/payments/test_webhook.py::test_p9_v11_provider_path_mismatch` | With `PAYMENT_PROVIDER=mock`, `POST /api/webhooks/payments/mercadopago/` returns 404 and stores nothing. |
| P9-V12 | API | `api/tests/api/payments/test_webhook.py::test_p9_v12_missing_or_malformed_signature` | A missing signature header returns 401 with `signature_ok = false`; a body altered after signing returns 401. |
| P9-V13 | integration | `api/tests/integration/payments/test_webhook.py::test_p9_v13_unknown_order_and_unknown_payment` | An unknown `external_reference` is marked processed with an error and alerted (PAY-19). A resource id the provider doesn't know (`PaymentNotFound`) is retried like any failure: 10 attempts with exponential backoff, then marked failed and alerted (G7, ADR-0044). |
| P9-V14 | concurrency | `api/tests/concurrency/test_webhooks.py::test_p9_v14_webhook_vs_reconcile_race` | Webhook processing and `reconcile_payments` for the same approved payment: one transition, and no exception surfaces (G14, ADR-0047). |
| P9-V15 | integration | `api/tests/integration/payments/test_refunds.py::test_p9_v15_refund_boundaries` | Refunding exactly the remaining balance succeeds; remaining + 1 centavo is rejected before calling the provider; two partials summing to the total end `refunded`. |
| P9-V16 | integration | `api/tests/integration/payments/test_refunds.py::test_p9_v16_oxxo_manual_refund_requires_note` | A manual OXXO refund without a note is rejected; with a note it applies the event with `actor="staff:<id>"`. |
| P9-V17 | integration | `api/tests/integration/payments/test_webhook.py::test_p9_v17_inline_failure_deferred` | A transient `fetch_payment` failure still returns 200 and leaves the row unprocessed; `process_webhooks` completes it later and increments `attempts`. A row that has failed 10 attempts is marked failed, is not retried again, and is alerted (G7, ADR-0044). |
| P9-V18 | concurrency | `api/tests/concurrency/test_mock_store.py::test_p9_v18_mock_store_atomic_writes` | Concurrent writes to one mock payment never leave invalid JSON on disk. |
| P9-V19 | API | `api/tests/api/orders/test_status.py::test_p9_v19_voucher_surfaced` | `voucher_url` and `voucher_expires_at` appear on the payment row and in the order status API. |
| P9-V20 | unit | `api/tests/unit/payments/test_signing.py::test_p9_v20_sign_verify` | `sign`/`verify` round-trip; a one-byte change fails; comparison uses `hmac.compare_digest`. |
| P9-V21 | integration | `api/tests/integration/payments/test_deadlines.py::test_p9_v21_voucher_generated_after_checkout_ttl` | The customer takes 31 minutes on the provider page, then generates an OXXO voucher; the `pending` notification arrives for an order already `expired`. The order stays `expired`, one alert is logged, and the mock payment ends `cancelled` (ADR-0046, OA-55). |

**Added in conversion:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P9-V22 | integration | `api/tests/integration/payments/test_refunds.py::test_p9_v22_refund_flags_issued_cfdi` | A full or partial refund of an order whose CFDI is issued sets `needs_review` on its request and lists it in the admin CFDI queue. A refund of an order with no issued CFDI changes no request. |
| P9-V23 | integration | `api/tests/integration/orders/test_cart_conversion.py::test_p9_v23_cart_converted_at_checkout` | A successful checkout sets `cart.converted_order` to the order; a failed one (an unavailable line) leaves it null. A second checkout from the cart with a new key creates no order and reserves nothing. The same key and body returns the original order. A fresh cart is created on the next add. (OA-58, ADR-0049) |

**Fixtures and factories introduced** (reused by later phases)

- `mock_provider` — `use_provider("PAYMENT_PROVIDER", "mock")` with a `tmp_path` store
- `mock_store` — direct read/write access to the JSON store
- `MockDriver` — the 9.13 driver; `deliver_notifications()`
- `signed_webhook(resource_id, notification_id, ts=None, secret=None)` — builds a request for the endpoint
- `stored_webhook_event` — a processed `webhook_event` row, for the `webhooks …` commands
- `pending_payment_order(method)` — an order in `pending_payment` with a mock payment of that method
- `issued_invoice_order` — a paid order whose `invoice_request` is `issued`, for the review-flag test

### Phase 10 — Fulfillment (mocked): delivery, pickup, pre-orders

**Deliverable:** the delivery path works end to end from the admin, against the mock carrier, together with the CFDI queue, the global-invoice export, the reporting exports and the packing view. In Release 2, pickup and pre-orders follow with the same stock rules.

**Release 1 scope:** delivery, the CFDI admin queue and global-invoice export, the reporting exports, and the packing view. Pickup, pre-orders and counter sales are R2.

#### 10.A How stock is reserved on each path

| Path | At checkout | On payment approved | On fulfillment | Release |
|---|---|---|---|---|
| **Home delivery** | `reserved += qty` at the delivery-source location; TTL by payment method | `on_hand -= qty`, `reserved -= qty`, ledger `sale_online` | Shipment created; no further stock movement | R1 |
| **Pickup** | Identical — same location, same pool. Pickup does not get a privileged reserve | Identical | Staff marks collected; no further stock movement. If the deadline lapses (T15), stock returns via `adjust_stock(reason='return')` | R2 |
| **Pre-order** | `variant.preorder_committed += qty`; reservation `kind='preorder'`, `location_id = NULL`; **`stock_item` untouched** | Reservation → `committed`. Still no `stock_item` movement — the goods do not exist yet | On receipt: `receive_stock()` then allocate FIFO; `on_hand -= qty` with ledger `sale_online` | R2 |

The critical property: **pre-orders never touch physical stock**, so they cannot starve delivery orders of units that are actually on the shelf (REQ-013).

#### Tasks

- [ ] **T10.9 — Mock carrier**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P10-V03
  - Depends on: Phase 9 closed
  - Context: §4.3 (Boundaries: Carrier)

`MockCarrier` — `apps/shipping/carriers/mock.py`, `code = "mock"`:

- **Tracking numbers.** If staff leave the tracking number blank, `create_shipment` generates `MOCK-<order number>-<n>`, where `n` is 1 + the number of shipments that order already has. The same order always gets the same sequence, so test runs and screenshots are reproducible. A number typed by staff is used as given.
- **Tracking URL.** `SITE_URL/dev/carrier/track/<tracking number>/`.
- **Storage.** State lives in `MOCK_STORE_DIR/carrier/<tracking number>.json`: the current status plus an event history. A new shipment starts `in_transit`. The store is outside the app database, for the same reason as 9.9.
- **`get_status`** returns the stored status; an unknown tracking number returns `UNKNOWN`.

- [ ] **T10.1 — Delivery shipments in the admin**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: [no-test: P10-V02 (T10.10) drives the shipment inline end to end; CAR-01 and CAR-02 (T10.13) cover `create_shipment`]
  - Depends on: T10.9
  - Context: §4.3 (Boundaries: Carrier); 8.A (T10)

Delivery: `ShipmentInline` on `OrderAdmin` — tracking number (optional when the active carrier can generate one) and optional cost. Saving it calls `providers.carrier().create_shipment(order, tracking_number=...)`, stores the returned `carrier`, `tracking_number` and `tracking_url`, and fires T10. In Part A, `MockCarrier` (T10.9) generates the tracking number and URL. No carrier API (A7). The production carrier is Phase 19.

- [ ] **T10.11 — Shipment status sync**
  - Release: R1 · Gate: task
  - REQs: REQ-022
  - Verifies: P10-V19
  - Depends on: T10.1
  - Context: §4.8; 8.A (T11)

`manage.py sync_shipments` — shared production code, run every 30 minutes (§4.8; add its line to `infra/crontab`). For each shipment of a `shipped` order with no `delivered_at`, call `providers.carrier().get_status(tracking_number)`:

- `DELIVERED` → set `delivered_at` and `apply_event(order, "marked_delivered", actor="carrier")` (T11).
- `EXCEPTION` → alert and add to the daily digest; no transition.
- `IN_TRANSIT` or `UNKNOWN` → nothing.

It never regresses a delivered shipment, and a second run is a no-op. Staff can still fire T11 at any time from the 8.5 action bar; with the manual carrier (Phase 19) that is the only path.

- [ ] **T10.10 — Mock tracking page**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P10-V02
  - Depends on: T10.11
  - Context: §4.3 (dev tools); 8.A (T10, T11, T12)

Mock tracking page `/dev/carrier/track/<tracking number>/`, registered only when `DEV_TOOLS_ENABLED` (404 in production). It shows the event history, the banner **"SIMULADOR — este envío no es real"**, and buttons **"En tránsito"**, **"Entregado"** and **"Incidencia"**. Each button updates the mock store and then runs `sync_shipments` for that shipment, so pressing "Entregado" moves the order to `delivered` through the production code path.

- [ ] **T10.12 — Mock carrier command**
  - Release: R1 · Gate: task
  - REQs: REQ-040
  - Verifies: P10-V04
  - Depends on: T10.10
  - Context: §4.3 (dev tools)

`manage.py mock_carrier advance <tracking number> --to in_transit|delivered|exception [--sync]` — the command-line equivalent of the T10.10 buttons. Refuses to run unless `DEV_TOOLS_ENABLED`.

- [ ] **T10.13 — Carrier contract suite**
  - Release: R1 · Gate: task
  - REQs: REQ-041
  - Verifies: P10-V01 (CAR-01 to CAR-07)
  - Depends on: T10.12
  - Context: §4.3; 9.13 (driver pattern)

Carrier contract suite — `tests/contract/carrier/`, written against a `CarrierDriver` in the same way as 9.13. `MockDriver` advances the mock store; `ManualDriver` arrives in Phase 19.

| ID | Scenario | Expected |
|---|---|---|
| CAR-01 | Create a shipment with a given tracking number | Returned as given, with a tracking URL |
| CAR-02 | Create a shipment without a tracking number | Either a deterministic generated number, or `TrackingNumberRequired` — and the admin form then requires the field |
| CAR-03 | `get_status` for a new shipment | Returns a `ShipmentStatus`; never raises |
| CAR-04 | Carrier reports `DELIVERED` | `sync_shipments` fires T11 once; a second run is a no-op |
| CAR-05 | Carrier reports `EXCEPTION` | Alert; no transition |
| CAR-06 | Unknown tracking number | `UNKNOWN`; no transition |
| CAR-07 | Staff fire T11, then `sync_shipments` runs | No second transition |

- [ ] **T10.17 — Packing view with bin locations**
  - Release: R1 · Gate: task
  - REQs: REQ-064
  - Verifies: P10-V26
  - Depends on: T10.1
  - Context: §4.4 (Pending schema changes); T4.8

The admin order page for an order in `preparing` shows a printable packing view: each line's SKU, product name, options and quantity, with its stock item's bin location (T4.8). Staff pick from it before creating the shipment (T10.1). Nothing on this view moves stock.

- [ ] **T10.14 — CFDI admin queue and recording**
  - Release: R1 · Gate: task
  - REQs: REQ-060
  - Verifies: P10-V23
  - Depends on: Phase 9 closed
  - Context: §4.3 (Boundaries: Invoicing), §4.4 (Invoicing tables, CFDI catalog codes); A8, A12
  - Open items: D16 (stand-in §2.5)

An admin view, "Facturas (CFDI)", over `invoice_request` (A8, ADR-0019):

- The queue lists paid orders whose request is `requested`, oldest first, followed by any request with `needs_review` (set by T9.14). Each row shows the order number, the paid date, the total and the fiscal data as the customer entered it.
- "Registrar CFDI" first calls `providers.invoicer().issue(request)`. With `INVOICE_PROVIDER=manual` it raises `ManualIssueRequired` (§4.3), and the form then requires the folio, the UUID (folio fiscal), the PDF and the XML. A missing value, a file over 5 MB or a file of the wrong type is a field error, and nothing is saved.
- Saving stores both files in `invoice_document` with their sha256 and size, sets the request to `issued` with `issued_at` and the staff user, and queues one `cfdi_issued` email (T11.8), all in one transaction.
- "Marcar revisado" clears `needs_review` and requires a note in `review_note`. "Cancelar CFDI" records a cancellation made outside the store: status `cancelled`, `cancelled_at`, and a required note. The store never decides the fiscal treatment (A12, D16).
- Staff only. The documents download from the admin and are never served from public media storage (§4.4).

- [ ] **T10.15 — Global-invoice export**
  - Release: R1 · Gate: task
  - REQs: REQ-060
  - Verifies: P10-V24
  - Depends on: T10.14
  - Context: §4.4; A8
  - Open items: D16 (stand-in §2.5)

An admin action, "Exportar para factura global": staff choose a date range, and the store returns a CSV of every order paid in that range that has no issued CFDI, excluding cancelled and expired orders and orders whose request is `issued`. Columns: order number, paid at (in the store timezone, G5), payment method, `total_cents` and `tax_included_cents`. Money stays in integer centavos (CR-01). The period the accountant uses, and how refunds after an export are handled, are D16.

- [ ] **T10.16 — Reporting exports**
  - Release: R1 · Gate: phase-close
  - REQs: REQ-063
  - Verifies: P10-V25
  - Depends on: T10.15, T10.17
  - Context: §4.4 (Pending schema changes); A19

Admin CSV exports for a date range, staff only, of orders, order lines and shipments. The owner builds the weekly dashboard and the monthly report from them outside the store (A19); the store adds no reporting screens. The columns follow G33's resolution (ADR-0030). They include each line's `unit_cost_cents` snapshot (T8.9); each order's `placed_at`, `paid_at`, `shipped_at` and `cancel_reason`; and each shipment's `shipped_at` and `delivered_at`, so shipping times and stock cancellations can be counted. Money stays in integer centavos (CR-01).

- [ ] **T10.5 — Pre-order reservations and capacity**
  - Release: R2 · Gate: —
  - REQs: REQ-013
  - Verifies: P10-V07, P10-V08, P10-V14, P10-V15, P10-V20
  - Depends on: T10.16; the R2 rows of 8.A (Phase 8)
  - Context: 10.A; §4.4
  - Open items: G36 (tests xfail until decided)

Pre-order capacity: if `preorder_limit` is set, `reserve()` must reject beyond it. If it is `NULL`, pre-orders are unlimited — make this visible in the admin, because unlimited pre-orders on an allocation-limited product is how a store ends up owing customers goods it cannot get.

- [ ] **T10.3 — Pre-order receiving**
  - Release: R2 · Gate: —
  - REQs: REQ-013
  - Verifies: P10-V09, P10-V16, P10-V17, P10-V21, P10-V22
  - Depends on: T10.5
  - Context: 10.A; 8.A (T9)
  - Open items: G9, G16 (tests xfail until decided)

Pre-order receiving — `apps/inventory/services.py`:

```python
@transaction.atomic
def receive_preorder_stock(variant, location, qty, *, actor) -> AllocationReport:
    """1. receive_stock(variant, location, qty)  -> ledger 'receipt'
       2. Find 'committed' preorder reservations for this variant whose orders
          are in 'awaiting_stock', oldest order.paid_at first (FIFO).
       3. For each, while units remain: consume from stock_item
          (on_hand -= qty, ledger 'sale_online'), mark the reservation settled,
          mark the order_line allocated.
       4. For each touched order: if EVERY preorder line is now allocated,
          apply_event(order, 'preorder_allocated')  -> T9.
       5. Any remainder stays as normal sellable stock."""
```

FIFO by `paid_at` is the fair and defensible rule. Write it down in the customer-facing pre-order terms. The "Recibir mercancía" admin action from T4.7 calls `receive_preorder_stock` for pre-order variants and `receive_stock` otherwise (G20).

- [ ] **T10.4 — Pre-order lifecycle**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P10-V18
  - Depends on: T10.3
  - Context: §4.8

Pre-order lifecycle on the variant: when `expected_release_date` has passed and `on_hand > 0`, a daily job (`refresh_preorder_flags`, §4.8) flips `is_preorder = false` so the product sells as normal stock. Until then the product page shows the release date.

- [ ] **T10.6 — Mixed orders**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P10-V10
  - Depends on: T10.3
  - Context: 10.A; A6
  - Open items: D8

Mixed orders (A6 / D8): an order with both in-stock and pre-order lines goes `paid → awaiting_stock`, and all of it waits. The in-stock lines are already committed (physically deducted), so they are safe. The order status page must say *"Se enviará completo a partir del {earliest_release_date}"*.

- [ ] **T10.2 — Pickup list in the admin**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P10-V05
  - Depends on: T10.16; the R2 rows of 8.A (Phase 8)
  - Context: 8.A (T8, T13); CR-47

Pickup: an admin list filtered to `state='ready_for_pickup'`, showing order number, customer name, phone, items, and `pickup_deadline_at`, with a "Entregado" button firing T13. Optimise this page for someone standing at a counter with a customer waiting: big rows, searchable by order number, one click.

- [ ] **T10.8 — Pickup deadline job**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P10-V06, P10-V12, P10-V13
  - Depends on: T10.2
  - Context: 8.A (T15); §4.8
  - Open items: D4 (stand-in §2.5); G10 (tests xfail until decided)

Pickup deadline job: T15 in `advance_orders`. Before cancelling, queue a reminder email at 24 hours remaining.

- [ ] **T10.7 — Counter sales reconciliation**
  - Release: R2 · Gate: —
  - REQs: REQ-011
  - Verifies: P10-V11
  - Depends on: T4.5, T4.10
  - Context: A11

Counter sales (A11): the admin page from T4.5, plus a `stock_ledger` filter by `reason='sale_in_store'` so the owner can reconcile the till against the system daily. Add this to the daily runbook (Phase 21) — it is the weak point of a no-POS design and depends on discipline, not code.

#### Verify — test specification

> Every ID below is a named test (§4.6). The phase closes when every in-scope ID passes in `make test-all` (§0.2). ⚠️ G# marks a test written against a gap's proposed resolution, `xfail(strict=True, reason="G#")` until the gap is decided (§2.4). `[R2]` marks an ID outside Release 1; `[manual]` an ID checked by hand in the phase-close report.

**From the original Verify items:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P10-V01 | contract | `api/tests/contract/carrier/test_suite_complete.py::test_p10_v01_all_scenarios_present_and_supported` · runs with `test_scenarios.py::test_car_01_…` to `test_car_07_…` | Every scenario ID CAR-01 to CAR-07 in T10.13 has a test; `MockDriver.supports()` is `True` for all; the scenarios pass with sockets disabled. |
| P10-V02 | integration | `api/tests/integration/fulfillment/test_delivery_flow.py::test_p10_v02_delivery_end_to_end` | Pay → `preparing`; an admin shipment with a blank tracking number stores `MOCK-<number>-1` and its URL → `shipped`; POST "Entregado" on the tracking page → `delivered` with `actor="carrier"`; clock + 7 days and `advance_orders` → `completed`. |
| P10-V03 | integration | `api/tests/integration/fulfillment/test_mock_carrier.py::test_p10_v03_tracking_numbers_deterministic` | A second shipment gets `-2`; a fresh database with the same order number reproduces the same numbers. |
| P10-V04 | integration | `api/tests/integration/fulfillment/test_devtools.py::test_p10_v04_carrier_devtools_absent_in_prod` | Under `prod.py`, `/dev/carrier/track/…` returns 404 and `mock_carrier advance` raises `CommandError`. |
| P10-V05 [R2] | integration | `api/tests/integration/fulfillment/test_pickup.py::test_p10_v05_pickup_flow` | Pay → `ready_for_pickup` → "Entregado" → `picked_up`, with `shipping_cents == 0` at every step. |
| P10-V06 [R2] | integration | `api/tests/integration/fulfillment/test_pickup.py::test_p10_v06_pickup_deadline_cancels_and_returns_stock` | Past its deadline the order is `cancelled`, `on_hand` is restored, and a `return` ledger row exists. |
| P10-V07 [R2] | integration | `api/tests/integration/fulfillment/test_preorder.py::test_p10_v07_preorder_leaves_stock_item_untouched` | Checkout increments `preorder_committed`; every `stock_item` column is byte-identical before and after. |
| P10-V08 [R2] | API | `api/tests/api/orders/test_preorder_checkout.py::test_p10_v08_preorder_limit_eleventh_rejected` | With `preorder_limit=10`, the 11th unit returns 409 with a Spanish message. |
| P10-V09 [R2] | integration | `api/tests/integration/fulfillment/test_preorder.py::test_p10_v09_partial_receipt_fifo` | 8 single-unit orders; receiving 5 allocates and transitions the 5 oldest by `paid_at`; 3 stay `awaiting_stock`; `on_hand` ends at 0. |
| P10-V10 [R2] | integration | `api/tests/integration/fulfillment/test_preorder.py::test_p10_v10_mixed_order_transitions_once` | A mixed order stays `awaiting_stock` until its pre-order line is allocated, then produces exactly one T9 event. |
| P10-V11 [R2] | integration | `api/tests/integration/fulfillment/test_counter_sale.py::test_p10_v11_counter_sale_ledger` | A counter sale reduces `on_hand` and writes a `sale_in_store` ledger row. |

**Added negative and edge cases:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P10-V12 [R2] | integration | `api/tests/integration/fulfillment/test_pickup.py::test_p10_v12_pickup_deadline_boundary` | At `now == pickup_deadline_at` the order is **not** cancelled; at + 1µs it is (T15 guard `<`). |
| P10-V13 [R2] | integration | `api/tests/integration/fulfillment/test_pickup.py::test_p10_v13_reminder_once_at_24h` | At 24 h 1 min remaining no reminder is sent; at 24 h one is sent; later runs send no duplicate. ⚠️ G10 |
| P10-V14 [R2] | integration | `api/tests/integration/fulfillment/test_preorder.py::test_p10_v14_limit_reached_exactly` | With `committed=9, limit=10`: reserving 1 succeeds and leaves `committed == 10`; the next unit is rejected; reserving 2 at 9 is rejected all-or-nothing. |
| P10-V15 [R2] | concurrency | `api/tests/concurrency/test_preorder.py::test_p10_v15_last_preorder_slot_race` | With `committed=9`, two threads race for the last slot: one wins and `committed == 10`. |
| P10-V16 [R2] | integration | `api/tests/integration/fulfillment/test_preorder.py::test_p10_v16_receipt_exceeds_preorders` | Receiving 10 against 8 pre-ordered allocates all 8 and leaves 2 sellable in `on_hand`. |
| P10-V17 [R2] | integration | `api/tests/integration/fulfillment/test_preorder.py::test_p10_v17_fifo_tie_break` | Two orders with identical `paid_at` and one unit available are allocated by the G9 rule. ⚠️ G9 |
| P10-V18 [R2] | integration | `api/tests/integration/fulfillment/test_preorder.py::test_p10_v18_refresh_preorder_flags_boundary` | Release date today with `on_hand > 0` flips `is_preorder`; tomorrow does not; `on_hand == 0` does not. |
| P10-V19 | integration | `api/tests/integration/fulfillment/test_sync_shipments.py::test_p10_v19_sync_never_regresses_delivered` | A later `in_transit` report keeps `delivered_at` and adds no event. |
| P10-V20 [R2] | integration | `api/tests/integration/fulfillment/test_admin.py::test_p10_v20_unlimited_preorder_flagged` | A pre-order variant with `preorder_limit IS NULL` shows a "sin límite" warning in the admin list. |
| P10-V21 [R2] | integration | `api/tests/integration/fulfillment/test_preorder.py::test_p10_v21_preorder_pickup_gets_deadline` | A pickup pre-order reaches `ready_for_pickup` through T9 with `pickup_deadline_at` set, so T15 can fire. ⚠️ G16 |
| P10-V22 [R2] | property | `api/tests/property/test_inventory_machine.py::test_p10_v22_preorder_rules` | `InventoryMachine` extended with pre-order reserve, receive and allocate never leaves `preorder_committed > preorder_limit` or touches `stock_item` for pre-order reservations. |

**Added in conversion:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P10-V23 | integration | `api/tests/integration/invoicing/test_admin_queue.py::test_p10_v23_queue_and_record` | The admin CFDI queue lists paid orders with a `requested` CFDI, oldest first. Recording the folio, UUID, PDF and XML marks the request `issued` and queues one `cfdi_issued` email. Saving without the UUID or either file shows field errors and changes nothing. `ManualInvoicer.issue()` raises `ManualIssueRequired`. |
| P10-V24 | integration | `api/tests/integration/invoicing/test_global_export.py::test_p10_v24_global_invoice_export` | The global-invoice export for a date range lists every paid order in it with no issued CFDI, with its total and IVA, and excludes cancelled, expired and invoiced orders. The range boundaries use the store timezone. |
| P10-V25 | integration | `api/tests/integration/reports/test_exports.py::test_p10_v25_csv_exports` | The admin CSV exports of orders, order lines and shipments for a date range contain the columns G33 defines, one row per record, money in integer centavos, and are available to staff only. |
| P10-V26 | integration | `api/tests/integration/fulfillment/test_packing.py::test_p10_v26_packing_view_bin_locations` | The admin order page lists each line with its stock item's bin location. |

**Fixtures and factories introduced** (reused by later phases)

- `shipped_order`
- `CarrierDriver` `MockDriver`; `mock_carrier_store`
- `invoice_request(order, status="requested")` and `cfdi_documents()` — a small valid PDF and XML pair, for the CFDI tests and the `cfdi_issued` email (T11.8)
- `export_rows(response)` — parses a CSV export into rows
- `[R2]` `ready_pickup_order`
- `[R2]` `preorder_variant(limit=None, release_date=…)`
- `[R2]` `awaiting_stock_orders(variant, n, paid_at_step=timedelta(minutes=1))`

### Phase 11 — Transactional email (local)

**Deliverable:** every order state change the customer cares about produces exactly one email, built from the Design System email components, with retries and without a message broker.

**Release 1 scope:** the seven R1 templates (§4.5), built from the DS email package, with their plain-text parts; the CFDI email carries the PDF and XML.

#### Tasks

- [ ] **T11.4 — Sender and Reply-To**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: [no-test: P11-V08 (T11.5) asserts the `Reply-To`]
  - Depends on: Phase 10 closed
  - Context: §4.7 (Core, Real-provider credentials)

A dedicated `noreply@` sender (`DEFAULT_FROM_EMAIL`, set in Phase 17) with a real `Reply-To` from `EMAIL_REPLY_TO` (§4.7), the store's monitored inbox.

- [ ] **T11.5 — File email sender**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P11-V08
  - Depends on: T11.4
  - Context: §4.3 (Interfaces: `OutgoingEmail`, `Attachment`; Boundaries: Email)

Sending goes through `providers.email_sender()`. In Part A, `EMAIL_PROVIDER=file` writes each email as `.html` and `.txt` to `EMAIL_FILE_DIR` (default `var/emails/`), and each attachment as `<same prefix>-<filename>` (§4.3). `EMAIL_MOCK_FAIL=1` forces send failures for testing the retry path (§4.3).

- [ ] **T11.6 — Vendor the Design System email HTML**
  - Release: R1 · Gate: task
  - REQs: REQ-055
  - Verifies: P11-V12
  - Depends on: T11.5, DSR-04 released, DSR-05 released
  - Context: §4.5 (Email); DS:email-components.md, DS:email-layouts.md
  - Open items: DSR-04, DSR-05 (blocking)
  - Done when: the vendored files match the DS version pinned in `web/package.json`.

Copy the compiled HTML of the pinned `@vinsmokemau/cup-noobles-email` version (its `dist/*.html`, including `reference.html`) into `api/apps/notifications/templates/email/ds/`, and write `ds-email-manifest.json` with the DS version and each file's sha256. A script, `scripts/vendor_ds_email.py`, does the copy from `web/node_modules`, so a DS upgrade task reruns it. The vendored files are never edited by hand.

The DS placeholders use the same `{{ slot_name }}` syntax as Django variables, so each vendored file loads as a Django template as it is. Django escapes variables by default; a slot that needs markup, such as order lines, waits for DSR-04 and is never marked safe by hand (§4.5).

- [ ] **T11.3 — Templates**
  - Release: R1 · Gate: task
  - REQs: REQ-052
  - Verifies: P11-V04, P11-V09
  - Depends on: T11.6
  - Context: §4.5 (Email); CR-32; 8.A

Templates (Spanish, `es-MX`), each built on the vendored DS reference layout (§4.5): a template is a subject line plus the values for the layout's slots, and its plain-text counterpart (T11.7). Every slot is filled with content from the order; components hold no copy of their own. The header's `{{ logo_url }}` is the raster logo the store hosts (DSR-05). Copy follows DS voice and microcopy (CR-32).

| Template | Trigger | Release |
|---|---|---|
| `order_confirmation` | T2 (T3 in R2) | R1 |
| `oxxo_voucher` | Pending cash payment — includes the ficha link and expiry | R1 |
| `order_expired` | T5 | R1 |
| `order_shipped` | T10 — includes tracking | R1 |
| `order_cancelled` | T6 / T16 (T15 in R2) | R1 |
| `refund_issued` | T17 / T18 | R1 |
| `cfdi_issued` | An invoice request recorded as issued (T10.14) — the PDF and XML attached | R1 |
| `verify_email` | Registration | R2 |
| `password_reset` | Reset request | R2 |
| `preorder_arrived` | T9 | R2 |
| `ready_for_pickup` | T8 — includes address, hours, and deadline | R2 |
| `pickup_reminder` | 24 h before the pickup deadline | R2 |

- [ ] **T11.7 — Plain-text counterparts**
  - Release: R1 · Gate: task
  - REQs: REQ-055
  - Verifies: P11-V01, P11-V13
  - Depends on: T11.3
  - Context: §4.5 (Email); DS:email-layouts.md (Plain-text counterpart)

Every template has a `text/plain` part built from the same slot values as its HTML, following the DS reference layout's counterpart: the blocks in the order of the parts, a blank line between blocks, every link written as its label, a colon and the full address, the logo as its alt text, and no markup. It carries every slot of the HTML except `{{ logo_url }}`.

- [ ] **T11.1 — Outbox sending**
  - Release: R1 · Gate: task
  - REQs: REQ-022
  - Verifies: P11-V02, P11-V05, P11-V06, P11-V10
  - Depends on: T11.7
  - Context: §4.8; T4.6
  - Open items: G17 (tests xfail until decided)

Outbox pattern: business code writes an `email_outbox` row inside the same transaction as the state change, through `enqueue_email()` (T4.6, G2). `manage.py send_outbox` (every minute; add its line to `infra/crontab`, §4.8) renders and sends pending rows, sets `sent_at`, and increments `attempts` with exponential backoff on failure. Give up after 6 attempts and alert.

- [ ] **T11.2 — Deduplication**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P11-V03, P11-V07
  - Depends on: T11.1
  - Context: §4.4 (`email_outbox`)

`dedupe_key` prevents duplicates when a webhook is delivered twice: `f"{order.id}:{template}"`. The partial unique index enforces it in the database.

- [ ] **T11.8 — CFDI email**
  - Release: R1 · Gate: phase-close
  - REQs: REQ-060
  - Verifies: P11-V11
  - Depends on: T11.2
  - Context: §4.3 (`Attachment`); §4.4 (Invoicing tables); T10.14

The `cfdi_issued` email names the order number and attaches the request's PDF and XML from `invoice_document`, as `Attachment` values on `OutgoingEmail` (§4.3). The outbox row carries the invoice request's id in its context, and `send_outbox` loads the documents at send time, so the files are never copied into the outbox. Its dedupe key is `f"{order.id}:cfdi_issued"`.

- [ ] **T11.9 — Release 2 templates**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P11-V14
  - Depends on: T11.8; the R2 work of Phases 6, 8 and 10
  - Context: §4.5 (Email); the 11.3 table (T11.3)

The R2 rows of the T11.3 table: `verify_email`, `password_reset`, `preorder_arrived`, `ready_for_pickup` and `pickup_reminder`, built the same way as the R1 templates, with their triggers.

#### Verify — test specification

> Every ID below is a named test (§4.6). The phase closes when every in-scope ID passes in `make test-all` (§0.2). ⚠️ G# marks a test written against a gap's proposed resolution, `xfail(strict=True, reason="G#")` until the gap is decided (§2.4). `[R2]` marks an ID outside Release 1; `[manual]` an ID checked by hand in the phase-close report.

**From the original Verify items:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P11-V01 | integration | `api/tests/integration/notifications/test_templates.py::test_p11_v01_every_template_renders[template]` | Every template of the release in progress renders HTML and text with factory context and matches its `syrupy` snapshot; the `string_if_invalid` sentinel never appears. |
| P11-V02 | integration | `api/tests/integration/notifications/test_outbox.py::test_p11_v02_failure_then_recovery` | With `EMAIL_MOCK_FAIL=1`, rows stay pending and `attempts` rises; unset, the next run sends them and the files exist. |
| P11-V03 | integration | `api/tests/integration/notifications/test_outbox.py::test_p11_v03_duplicate_webhook_one_confirmation` | A duplicated approval notification yields exactly one `order_confirmation` row and one file. |
| P11-V04 | integration | `api/tests/integration/notifications/test_templates.py::test_p11_v04_no_template_syntax_leaks[template]` | Rendered output contains no `{{`, `{%` or the sentinel; the HTML declares `lang="es-MX"`. *The human review that the copy reads as correct Spanish moves to Phase 17.* |

**Added negative and edge cases:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P11-V05 | integration | `api/tests/integration/notifications/test_outbox.py::test_p11_v05_backoff_and_give_up` | Retry delays grow exponentially; after the 6th failure there are no more attempts and `error_reporter().capture_message` is called. |
| P11-V06 | integration | `api/tests/integration/notifications/test_outbox.py::test_p11_v06_outbox_rolls_back_with_transaction` | A state change whose transaction rolls back leaves no outbox row. |
| P11-V07 | integration | `api/tests/integration/notifications/test_outbox.py::test_p11_v07_dedupe_key_unique` | Enqueuing the same `dedupe_key` twice leaves one row, and the caller sees no exception. |
| P11-V08 | unit | `api/tests/unit/notifications/test_file_sender.py::test_p11_v08_file_names_and_reply_to` | Files are named `<ts>-<template>-<outbox id>.html` and `.txt`; `OutgoingEmail.reply_to` is `EMAIL_REPLY_TO` (§4.7). |
| P11-V09 | integration | `api/tests/integration/notifications/test_triggers.py::test_p11_v09_each_trigger_queues_its_template[trigger]` | Every R1 trigger in the T11.3 table queues exactly its template: T2, pending OXXO, T5, T10, T6/T16, and T17/T18. (`cfdi_issued` is P11-V11.) |
| P11-V10 | concurrency | `api/tests/concurrency/test_outbox.py::test_p11_v10_overlapping_send_outbox_runs` | Two overlapping `send_outbox` runs send every row exactly once. ⚠️ G17 |

**Added in conversion:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P11-V11 | integration | `api/tests/integration/notifications/test_cfdi_email.py::test_p11_v11_cfdi_issued_with_attachments` | The `cfdi_issued` email names the order number and carries the PDF and XML as attachments. It is queued once per issued request (dedupe key). `FileEmailSender` writes the attachments next to the `.html`. |
| P11-V12 | integration | `api/tests/integration/notifications/test_ds_email.py::test_p11_v12_templates_built_from_vendored_ds_html` | Every R1 template is built from the vendored DS email HTML: each vendored file's sha256 matches `ds-email-manifest.json`; the manifest's version equals the DS version pinned in `web/package.json`; no rendered template contains a color, font-family or size literal absent from the vendored files. |
| P11-V13 | integration | `api/tests/integration/notifications/test_plain_text.py::test_p11_v13_text_part_complete[template]` | Every R1 email has a `text/plain` part that contains every text and every link address of its HTML part, in order (DS:email-layouts.md). |
| P11-V14 [R2] | integration | `api/tests/integration/notifications/test_triggers.py::test_p11_v14_r2_triggers_queue_their_template[trigger]` | Every R2 trigger in the T11.3 table queues exactly its template: T3, T8, T9, T15, registration, reset, and the pickup reminder. |

**Fixtures and factories introduced** (reused by later phases)

- `mailbox` — parses the files in `EMAIL_FILE_DIR` into messages, with their attachments
- `failing_email_sender` — `EMAIL_MOCK_FAIL=1`
- `template_context(template)` — factory-built context per template; syrupy `snapshot`
- `vendored_ds_email` — loads `ds-email-manifest.json` and the vendored files

### Phase 12 — Frontend foundation and catalog pages

**Deliverable:** the site shell and the browsable catalog — home, catalog with facets, category, product, search, legal pages, and the pre-launch page — server-rendered, in Spanish, assembled from the Design System layer, and working at 360px wide. The shared composable `useApi`, the `formatMXN` helper, and the catalog components are built and tested here and reused by every later frontend phase.

**Release 1 scope:** all tasks except `useAuth` and the home page's open pre-orders (R2), plus the "próximamente" page (G32), the styling scan and the DS pin check.

#### 12.A Pages

| Route | File | Notes |
|---|---|---|
| `/` | `pages/index.vue` | Hero, featured products (G28), categories. Open pre-orders: R2 (T12.17) |
| `/catalogo` | `pages/catalogo/index.vue` | Grid + filter sidebar driven by `/api/catalog/facets/` |
| `/catalogo/[categoria]` | `pages/catalogo/[categoria].vue` | Same component, category-scoped |
| `/producto/[slug]` | `pages/producto/[slug].vue` | Gallery, variant selector, attribute table, availability, add to cart (wired in Phase 13) |
| `/buscar` | `pages/buscar.vue` | |
| `/legal/{terminos,privacidad,envios,devoluciones}` | | Content from D2 |

While pre-launch mode is on (T5.7), every route above shows the "próximamente" page to anonymous visitors (T12.15, G32).

#### Tasks

- [ ] **T12.1 — Nuxt configuration**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: [no-test: P12-V01 (T12.16) and P12-V25 (T12.10) prove the server-rendering path]
  - Depends on: Phase 11 closed
  - Context: §4.1, §4.5 (Packages); G18
  - Open items: G18 (tests xfail until decided)

`nuxt.config.ts`: `ssr: true`, `extends: ['@vinsmokemau/cup-noobles-nuxt']`, `modules: ['@nuxt/image', '@nuxtjs/sitemap']`. Do not register `@nuxt/ui`: the layer does (C-11). `runtimeConfig.public.apiBase = '/api'` — a relative path, because same-origin. `nitro.devProxy` points `/api` at the local Django container for development; the server-rendering route in a production build follows G18's proposed resolution (Nitro `routeRules` proxying `/api/**` to a server-only API target).

- [ ] **T12.14 — Styling scan and Design System pin check**
  - Release: R1 · Gate: task
  - REQs: REQ-050
  - Verifies: P12-V26, P12-V27
  - Depends on: T12.1
  - Context: §4.5 (Consumption rules); CR-26, CR-27
  - Open items: DSR-09 (the scan is the fallback until released)

- `web/tests/architecture/styling.test.ts` scans `web/app/**` for Tailwind color, border, radius, shadow, ring, font and arbitrary-value utilities, and for `style` attributes and `<style>` blocks with a visual value. Layout utilities pass: display, flex and grid, gap, spacing, sizing, position and overflow. A fixture file with one violation of each kind must fail the scan.
- `web/tests/architecture/ds-pin.test.ts` checks that `web/package.json` pins the three DS packages at one exact version and has no direct `@nuxt/ui` or `tailwindcss` dependency, and that `nuxt.config.ts` extends the layer.
- When the DS publishes its raw-value lint rule (DSR-09), add it to the ESLint configuration as well.

The scan runs early so every later task is checked as it goes.

- [ ] **T12.2 — `useApi`**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P12-V05, P12-V06, P12-V07
  - Depends on: T12.1
  - Context: §4.1; CR-29

`app/composables/useApi.ts` — one thin `$fetch` wrapper that:

- prefixes `/api`
- forwards cookies during SSR (`useRequestHeaders(['cookie'])`) so the server render sees the session (a staff session in R1, a customer in R2)
- attaches `X-CSRFToken` from the `csrftoken` cookie on unsafe methods
- maps DRF error shapes to a single `ApiError { status, detail, fieldErrors }`

Every request in the app goes through this. No bare `$fetch` calls anywhere else (CR-29).

- [ ] **T12.11 — Lint rule for `$fetch`**
  - Release: R1 · Gate: task
  - REQs: REQ-054
  - Verifies: P12-V24
  - Depends on: T12.2
  - Context: CR-29

ESLint `no-restricted-syntax` rule: a call to `$fetch` anywhere except `app/composables/useApi.ts` is an error. This enforces the T12.2 rule mechanically.

- [ ] **T12.6 — Money formatting**
  - Release: R1 · Gate: task
  - REQs: REQ-001, REQ-052
  - Verifies: P12-V09
  - Depends on: T12.1
  - Context: §4.5 (Formatting); CR-30; DS:formatting.md
  - Done when: `/ui-review` ran (§0.5); findings fixed or registered.

`PriceDisplay` and the `formatMXN` helper in `app/utils/money.ts` are the **only** places money is formatted: `new Intl.NumberFormat('es-MX', {style:'currency', currency:'MXN'}).format(cents / 100)`, with no suffix (ADR-0024, CR-30). The locale and the currency code live in `app/utils/money.ts` and nowhere else (§4.5).

- [ ] **T12.4 — Catalog components**
  - Release: R1 · Gate: task
  - REQs: REQ-051, REQ-052, REQ-054
  - Verifies: P12-V04, P12-V10, P12-V12
  - Depends on: T12.6, DSR-01 released, DSR-02 released, DSR-03 released
  - Context: §4.5 (Composition map, Consumption rules); CR-26, CR-27
  - Open items: DSR-01, DSR-02, DSR-03 (blocking)
  - Done when: `/ui-review` ran (§0.5); findings fixed or registered.

Catalog components, built from DS parts per the §4.5 composition map (do not hand-roll these, CR-26): `ProductCard`, `ProductGallery`, `VariantSelector`, `AttributeTable` (renders `product_type.attribute_schema` titles against `product.attributes`), `AvailabilityBadge`, `PriceDisplay` (the single place that formats centavos, through `formatMXN` — T12.6), `FilterSidebar`. The components add no visual styling of their own (CR-27); text arrives through props and slots (CR-32).

- [ ] **T12.5 — Attribute table**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P12-V11
  - Depends on: T12.4
  - Context: §4.4 (attribute-agnostic catalog)
  - Done when: `/ui-review` ran (§0.5); findings fixed or registered.

`AttributeTable` is what makes the attribute-agnostic model pay off visually: it reads the type's schema for labels and ordering, so a new category renders a correct spec table with zero frontend work.

- [ ] **T12.16 — Catalog pages**
  - Release: R1 · Gate: task
  - REQs: REQ-053
  - Verifies: P12-V01, P12-V13, P12-V14, P12-V15, P12-V16, P12-V17, P12-V18
  - Depends on: T12.5
  - Context: 12.A; §4.5
  - Open items: G18 (tests xfail until decided); D2 (stand-in §2.4: placeholder pages)
  - Done when: `/ui-review` ran (§0.5); findings fixed or registered.

Build the 12.A routes from the T12.4 components, fetching through `useApi` with `useFetch` or `useAsyncData` so the first render happens on the server:

- home: featured products (G28, ADR-0030) and categories
- catalog grid with the facet sidebar driven by `/api/catalog/facets/`, with filters reflected in the URL
- the category page, the same component scoped to a category
- the product page: gallery, variant selector, attribute table and availability (add to cart arrives in Phase 13)
- search
- the four legal pages, rendering the D2 placeholder

- [ ] **T12.10 — Error page**
  - Release: R1 · Gate: task
  - REQs: REQ-053
  - Verifies: P12-V03, P12-V25
  - Depends on: T12.16
  - Context: §4.5 (Composition map); G18
  - Open items: G18 (tests xfail until decided)
  - Done when: `/ui-review` ran (§0.5); findings fixed or registered.

`error.vue`, built from the DS error-page pattern (§4.5). A failed API call must show a retry affordance, never a blank page.

- [ ] **T12.13 — Real 404 for unknown products**
  - Release: R1 · Gate: task
  - REQs: REQ-053
  - Verifies: P12-V20
  - Depends on: T12.10
  - Context: 12.A
  - Done when: `/ui-review` ran (§0.5); findings fixed or registered.

The product page calls `createError({ statusCode: 404 })` when the API returns 404, so unknown slugs render `error.vue` with a real 404 status and `noindex`.

- [ ] **T12.7 — SEO**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P12-V23
  - Depends on: T12.16
  - Context: 12.A
  - Done when: `/ui-review` ran (§0.5); findings fixed or registered.

SEO: `useSeoMeta` on every page; `Product` JSON-LD with `offers.availability` and `priceCurrency: "MXN"` on product pages; `@nuxtjs/sitemap` generating from the catalog API; canonical URLs; OG images from the primary product image.

- [ ] **T12.8 — Images**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: [no-test: the Lighthouse budgets (P12-V02, T12.12) catch layout shift; P12-V01 checks the product page's server render]
  - Depends on: T12.16
  - Context: §4.3 (Boundaries: Media storage); DS:ADR-0056, DS:ADR-0057
  - Open items: DSR-07
  - Done when: `/ui-review` ran (§0.5); findings fixed or registered.

Images: `@nuxt/image` (`none` provider in Part A, since derivatives are pre-generated — §4.3), `loading="lazy"` below the fold, explicit `width`/`height` to prevent layout shift. Product photos follow the DS photo standards (DS:ADR-0056, DS:ADR-0057; DSR-07 for packaging photos): `CnMediaCard` shows the whole picture in a 4:3 frame, and the brand d20 when a picture is missing.

- [ ] **T12.9 — Accessibility and mobile**
  - Release: R1 · Gate: task
  - REQs: REQ-051
  - Verifies: P12-V19, P12-V21
  - Depends on: T12.13, T12.7, T12.8
  - Context: §4.6 (Accessibility); CR-33, CR-35, CR-36
  - Done when: `/ui-review` ran (§0.5); findings fixed or registered.

Accessibility and mobile: real `<button>` and `<a>` elements, labelled inputs, the DS focus ring (DS:ADR-0009; never restyled), 44px minimum tap targets through DS size props (CR-36), tested at 360px wide. Most Mexican e-commerce traffic is mobile.

- [ ] **T12.15 — Pre-launch page**
  - Release: R1 · Gate: task
  - REQs: REQ-062
  - Verifies: P12-V28
  - Depends on: T12.9
  - Context: §4.5 (Composition map); T5.7; CR-47
  - Open items: D17
  - Done when: `/ui-review` ran (§0.5); findings fixed or registered.

Per G32 (ADR-0038): while pre-launch mode is on (T5.7), every storefront route renders a "próximamente" page for anonymous visitors, with status 200 and `noindex`, built from `CnLogo`, a DS motif and `CnMediaCard` (§4.5). The API decides: during the server render the page asks the API for the mode with the forwarded cookie, so a staff session sees the catalog. The page shows no date or countdown, and never presents the warehouse as a store (CR-47). Whether it links to an interest list follows D17 (no link until decided).

A dev-only toggle, `POST /dev/test/prelaunch/`, registered only when `DEV_TOOLS_ENABLED` (404 in production), lets E2E specs switch the mode.

- [ ] **T12.12 — Lighthouse budgets**
  - Release: R1 · Gate: phase-close
  - REQs: —
  - Verifies: P12-V02
  - Depends on: T12.15, T12.14
  - Context: §4.6

Lighthouse CI: `web/lighthouserc.json` with the mobile preset against `/`, `/catalogo` and one seeded product page, asserting Performance ≥ 85, SEO ≥ 95, Accessibility ≥ 90. It runs in `make test-all` (§0.3).

- [ ] **T12.3 — `useAuth`**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P12-V08, P12-V22
  - Depends on: T12.12; the R2 work of Phase 6
  - Context: §4.1
  - Open items: G18 (tests xfail until decided)

`app/composables/useAuth.ts` — `useState('me')` populated by `/api/auth/me/` in a plugin during SSR.

- [ ] **T12.17 — Home: open pre-orders**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P12-V29
  - Depends on: T12.12; the R2 work of Phase 10
  - Context: 12.A
  - Done when: `/ui-review` ran (§0.5); findings fixed or registered.

The home page's open pre-orders section: seeded pre-order products with their release date and a working link (12.A).

#### Verify — test specification

> Every ID below is a named test (§4.6). The phase closes when every in-scope ID passes in `make test-all` (§0.2). ⚠️ G# marks a test written against a gap's proposed resolution, `xfail(strict=True, reason="G#")` until the gap is decided (§2.4). `[R2]` marks an ID outside Release 1; `[manual]` an ID checked by hand in the phase-close report.

**From the original Verify items:**

| Test ID | Layer | File | Assertion |
|---|---|---|---|
| P12-V01 | SSR | `web/e2e/p12_ssr.spec.ts` › `p12_v01 product HTML contains name and price` | `request.get('/producto/<seeded slug>')` returns raw HTML (no JavaScript executed) that contains the product name, the `formatMXN` price, and JSON-LD with `offers.price` and `priceCurrency: "MXN"`. ⚠️ G18 |
| P12-V02 | performance | `web/tests/perf/lighthouse.test.ts` › `p12_v02 lighthouse budgets` | Runs `lhci collect` and `lhci assert` against the compose stack; every budget in T12.12 holds on all three pages. |
| P12-V03 | E2E | `web/e2e/p12_errors.spec.ts` › `p12_v03 api failure shows retry not blank` | During client-side navigation with `page.route('/api/**')` returning 500, the page shows an error state with "Reintentar"; after `unroute`, pressing it recovers the content. |
| P12-V04 | contract | `web/tests/contract/type-drift.test.ts` › `p12_v04 renamed field fails vue-tsc` | Renaming a product field in a temporary copy of `openapi.snapshot.yml`, regenerating types into a temporary directory, and running `vue-tsc --noEmit` against them exits non-zero at the component that uses the field. |

**Composables, helpers and components:**

| Test ID | Layer | File | Assertion |
|---|---|---|---|
| P12-V05 | unit | `web/tests/unit/composables/useApi.test.ts` › `p12_v05 csrf header on unsafe methods only` | POST, PUT, PATCH and DELETE send `X-CSRFToken` equal to the `csrftoken` cookie; GET and HEAD never send it. |
| P12-V06 | unit | `web/tests/unit/composables/useApi.test.ts` › `p12_v06 forwards cookies during SSR` | On the server (`useRequestHeaders` stubbed via `mockNuxtImport`), the outgoing request carries the incoming `cookie` header; on the client no `cookie` header is set by hand. |
| P12-V07 | unit | `web/tests/unit/composables/useApi.test.ts` › `p12_v07 maps DRF errors` | `400 {field: [msg]}` → `fieldErrors.field`; `400 {non_field_errors}` → `detail`; `403`/`404 {detail}` → `detail`; `429` → status 429 with a Spanish message; a network failure → status 0. Every case yields an `ApiError`. |
| P12-V08 [R2] | unit | `web/tests/unit/composables/useAuth.test.ts` › `p12_v08 me populated shared and cleared` | The plugin fills `me` from `/api/auth/me/` (`registerEndpoint`); a 401 yields `null` without throwing; two components see the same state; `logout()` clears it. |
| P12-V09 | unit | `web/tests/unit/utils/money.test.ts` › `p12_v09 formatMXN` | `123400 → "$1,234.00"`, `0 → "$0.00"`, `5 → "$0.05"`, `100000000 → "$1,000,000.00"`; non-integer input throws. (ADR-0024) |
| P12-V10 | component | `web/tests/components/VariantSelector.test.ts` › `p12_v10 selects variant from axes` | For the hoodie fixture, it renders `talla` and `color` groups from the resolved axes. Choosing M + negro emits that variant's `public_id`. An out-of-stock combination is disabled and labelled "Agotado". A single-variant product renders no selector. Arrow keys move within each radio group. |
| P12-V11 | component | `web/tests/components/AttributeTable.test.ts` › `p12_v11 renders brand-new type from schema` | A product whose type code and schema are generated inside the test renders one row per schema property: the property `title` as the label, in schema order, with booleans shown as "Sí"/"No". Keys missing from `attributes` are omitted, and keys absent from the schema are not rendered. A source scan asserts `AttributeTable.vue` references no product-type code. |
| P12-V12 | component | `web/tests/components/AvailabilityBadge.test.ts` › `p12_v12 status labels` | `in_stock` "Disponible", `low_stock` "Últimas piezas", `out_of_stock` "Agotado", `preorder` "Preventa · llega el 15 de noviembre de 2026" (es-MX date). The status is conveyed in text, not colour alone. |

**Pages (Playwright, both projects):**

| Test ID | Layer | File | Assertion |
|---|---|---|---|
| P12-V13 | E2E | `web/e2e/p12_catalog.spec.ts` › `p12_v13 home shows featured products` | Seeded featured products appear on the home page, with working links. |
| P12-V14 | E2E | `web/e2e/p12_catalog.spec.ts` › `p12_v14 facet filter updates results and url` | Choosing "Línea: Nendoroid" adds `attr.linea` to the URL and shows only matching products; the browser back button restores the unfiltered list. |
| P12-V15 | E2E | `web/e2e/p12_catalog.spec.ts` › `p12_v15 category page is scoped` | `/catalogo/<category>` lists only that category's products. |
| P12-V16 | E2E | `web/e2e/p12_product.spec.ts` › `p12_v16 variant selection updates price and availability` | Selecting a hoodie variant updates the displayed price and badge to that variant's values from the API. |
| P12-V17 | E2E | `web/e2e/p12_search.spec.ts` › `p12_v17 search tolerates a typo` | Both the exact query and a one-letter misspelling return the seeded product. |
| P12-V18 | E2E | `web/e2e/p12_legal.spec.ts` › `p12_v18 legal pages render` | All four legal routes return 200 and render their content (the D2 placeholder in Part A). |
| P12-V19 | a11y | `web/e2e/p12_a11y.spec.ts` › `p12_v19 axe on every catalog page` | `expectNoA11yViolations` passes on each 12.A route, on both projects. |

**Added negative and edge cases:**

| Test ID | Layer | File | Assertion |
|---|---|---|---|
| P12-V20 | E2E | `web/e2e/p12_product.spec.ts` › `p12_v20 unknown product is a real 404` | The response status is 404; `error.vue` links back to the catalog; the page carries `noindex`. |
| P12-V21 | E2E | `web/e2e/p12_mobile.spec.ts` › `p12_v21 no horizontal scroll at 360px` | On every 12.A route, `documentElement.scrollWidth <= 360`, and header and product-page controls are at least 44px tall. |
| P12-V22 [R2] | SSR | `web/e2e/p12_ssr.spec.ts` › `p12_v22 ssr sees the logged-in customer` | A raw-HTML request carrying a session cookie renders the customer's name in the header, which proves cookie forwarding end to end. ⚠️ G18 |
| P12-V23 | E2E | `web/e2e/p12_seo.spec.ts` › `p12_v23 sitemap canonical and json-ld` | `/sitemap.xml` lists active products and excludes draft and archived ones; product pages carry a canonical URL, `og:image`, and JSON-LD that parses. |
| P12-V24 | unit | `web/tests/unit/lint-rules.test.ts` › `p12_v24 bare $fetch forbidden` | The T12.11 ESLint rule flags a fixture file calling `$fetch` and passes `useApi.ts`. |
| P12-V25 | E2E | `web/e2e/p12_errors.spec.ts` › `p12_v25 ssr with api down renders error page` | With the stack's API target pointed at an unreachable address, a raw request renders `error.vue` with a 5xx status — never an empty body. ⚠️ G18 |

**Added in conversion:**

| Test ID | Layer | File | Assertion |
|---|---|---|---|
| P12-V26 | architecture | `web/tests/architecture/styling.test.ts` › `p12_v26 no visual styling in the storefront` | A scan of `web/app/**` finds no Tailwind color, border, radius, shadow, ring, font or arbitrary-value utility, and no `style` attribute or `<style>` block with a visual value. A fixture file with one of each fails the scan; the real tree passes. |
| P12-V27 | architecture | `web/tests/architecture/ds-pin.test.ts` › `p12_v27 ds packages pinned and layer extended` | `web/package.json` pins the three DS packages at one exact version and lists no direct `@nuxt/ui` or `tailwindcss` dependency; `nuxt.config.ts` extends `@vinsmokemau/cup-noobles-nuxt`. |
| P12-V28 | E2E | `web/e2e/p12_prelaunch.spec.ts` › `p12_v28 prelaunch page for anonymous visitors` | With pre-launch mode on, an anonymous visit to `/`, `/catalogo` and a product URL shows the "próximamente" page with status 200 and `noindex`; a staff session sees the catalog. |
| P12-V29 [R2] | E2E | `web/e2e/p12_catalog.spec.ts` › `p12_v29 home shows open preorders` | The seeded open pre-order appears on the home page with its release date and a working link. |

**Fixtures and factories introduced** (reused by later phases)

- `web/tests/fixtures/*.ts` — payloads typed as `components['schemas'][…]` from `app/types/api.d.ts` (`productDetail`, `hoodie`, `newTypeProduct`, `catalogPage`), so any drift from the API contract fails `vue-tsc`
- `mountWithApi(component, endpoints)` — `mountSuspended` plus `registerEndpoint` in one helper
- Playwright `seed` fixture — reads `var/e2e/manifest.json`, written by `seed_e2e` (first built in T1.13b; each phase adds its own seeded data and T15.2 completes it), so specs never hard-code slugs, SKUs or emails
- Playwright `staffLogin(page)` — logs in to the Django admin as the seeded staff user, so the session cookie reaches the storefront
- Playwright `setPrelaunch(on)` — calls the dev-only toggle from T12.15

### Phase 13 — Frontend cart and checkout

**Deliverable:** add-to-cart from the product page, the cart, the single-page checkout for delivery with an optional CFDI request, the hand-off to the payment simulator, and the three post-payment landing pages, all driven by server state through `useCart`.

**Release 1 scope:** delivery only; the "Quiero factura" section; the purchase-limit message; the order-status token and pay-retry endpoints the landing pages need (G21, G22).

#### 13.A Pages

| Route | File | Notes |
|---|---|---|
| `/carrito` | `pages/carrito.vue` | |
| `/checkout` | `pages/checkout.vue` | Single page: contact → delivery → invoice (optional) → review |
| `/pedido/[id]/gracias` | | Post-payment landing; polls order state |
| `/pedido/[id]/pendiente` | | OXXO/SPEI: shows the voucher prominently |
| `/pedido/[id]/error` | | Retry link |

#### Tasks

- [ ] **T13.8 — Dev inspection endpoints**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: [no-test: used by P13-V02 and P13-V18; P15-V11 (Phase 15) checks they are absent in production]
  - Depends on: Phase 12 closed
  - Context: §4.3 (dev tools)

Dev inspection endpoints for tests, registered only when `DEV_TOOLS_ENABLED` (404 in production, like 9.10):

- `GET /dev/test/inventory/<sku>/` → `{on_hand, reserved, preorder_committed}`
- `GET /dev/test/orders/?email=<email>` → the orders for that email with state and number

They are read-only, and they let E2E specs assert stock and order effects without scraping the admin.

- [ ] **T13.1 — `useCart`**
  - Release: R1 · Gate: task
  - REQs: REQ-002
  - Verifies: P13-V03, P13-V04
  - Depends on: T13.8
  - Context: §4.1 (cart in the database); CR-02, CR-24

`app/composables/useCart.ts` — `useState('cart')` holding the server's cart response, plus `add/update/remove/setFulfillment` which call the API and **replace state with the server's response**. Never mutate the local object optimistically; the server is the only place totals exist.

- [ ] **T13.2 — Cart and address components**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P13-V05, P13-V06, P13-V07
  - Depends on: T13.1
  - Context: §4.5 (Composition map); CR-26, CR-28
  - Done when: `/ui-review` ran (§0.5); findings fixed or registered.

Cart and checkout components, built from DS parts per the §4.5 composition map (do not hand-roll these, CR-26): `CartLine`, `AddressForm` (with postal-code autofill from T6.6). Forms use `UForm` with one Zod schema each (CR-28).

- [ ] **T13.13 — Cart page**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P13-V09, P13-V10
  - Depends on: T13.2
  - Context: 13.A; 7.4
  - Done when: `/ui-review` ran (§0.5); findings fixed or registered.

`/carrito` (13.A): `CartLine` rows from `useCart` state; the server's per-line availability messages (`reduced` with `max_available`, `unavailable` — 7.4); totals from the server; the DS empty-state pattern with a link to the catalog when the cart is empty; and the button to the checkout.

- [ ] **T13.5 — Add to cart and the header badge**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P13-V08
  - Depends on: T13.13
  - Context: 12.A
  - Done when: `/ui-review` ran (§0.5); findings fixed or registered.

Wire the product page's add-to-cart button (12.A) to `useCart().add`, and add a header cart badge that reads `useCart` state.

- [ ] **T13.9 — Order-status token**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P13-V26
  - Depends on: T13.8
  - Context: 8.A (T1); 9.B; 6.7
  - Open items: G21 (tests xfail until decided)

Per G21's proposed resolution: at T1 the API issues a short-lived signed token for the order (Django signing, with an expiry decided with G21), carried in the provider's `back_urls` (`/pedido/{public_id}/gracias?t=…`, and likewise `pendiente` and `error`). `GET /api/orders/{public_id}/status/?t=<token>` returns the order's public status fields — state, number, total, and the voucher URL and expiry if one is pending. It is read-only, is not subject to the guest-lookup limit (6.7), and returns the same 404 body for a missing, expired or tampered token.

- [ ] **T13.10 — Pay retry**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P13-V27
  - Depends on: T13.9
  - Context: 8.A (T1, T4); 9.B
  - Open items: G22 (tests xfail until decided)

Per G22's proposed resolution: `POST /api/orders/{public_id}/pay/`, authorised by the order-status token (T13.9), returns a fresh `checkout_url` from `payment_provider().create_checkout(order)` while the order is `pending_payment`, keeping its reservations and its deadline. Any other state returns 409. The cart is marked converted at T1 (T9.16, ADR-0049), so retrying from the cart cannot create a second order holding a second set of stock.

- [ ] **T13.3 — Checkout page**
  - Release: R1 · Gate: task
  - REQs: REQ-021
  - Verifies: P13-V01, P13-V02, P13-V11, P13-V21
  - Depends on: T13.5, T13.10
  - Context: 13.A; 8.4; §2.5 (D5); CR-02
  - Open items: D5 (stand-in §2.5)
  - Done when: `/ui-review` ran (§0.5); findings fixed or registered.

Checkout page — deliberately one page, collapsible sections, no wizard:

1. **Contacto** — email, phone
2. **Entrega** — the address form (`AddressForm`) for home delivery. The shipping quote updates on postal-code change.
3. **Factura** — optional; "Quiero factura" (T13.11)
4. **Revisión** — lines, totals, "Pagar" button

"Pagar" calls `POST /api/checkout/` with an `Idempotency-Key` (a UUID generated once when the page mounts), then `window.location.href = checkout_url`. Disable the button while in flight.

In R2, Contacto prefills the email of a logged-in customer, Entrega gains the pickup option, and Revisión shows the pre-order notice (T13.14).

- [ ] **T13.11 — "Quiero factura"**
  - Release: R1 · Gate: task
  - REQs: REQ-060
  - Verifies: P13-V23
  - Depends on: T13.3
  - Context: §4.4 (Invoicing tables, CFDI catalog codes); T8.7; CR-28, CR-32
  - Open items: D16 (stand-in §2.5)
  - Done when: `/ui-review` ran (§0.5); findings fixed or registered.

The checkout's Factura section: a checkbox, "Quiero factura", reveals the fiscal fields as DS form fields — RFC, nombre o razón social, código postal fiscal, régimen fiscal and uso de CFDI. Régimen and uso are selects whose options come from the API's CFDI catalog (`api/fixtures/cfdi_catalogs.json`, §4.4); this task adds the read-only, cacheable `GET /api/invoicing/cfdi-catalogs/` that serves them. Zod checks formats on the client; the server's field errors (P8-V19) render under the matching inputs through `ApiError.fieldErrors`. Unchecking the box sends no invoice data. Copy follows DS microcopy (CR-32).

- [ ] **T13.6 — Checkout errors**
  - Release: R1 · Gate: task
  - REQs: REQ-002, REQ-010
  - Verifies: P13-V17, P13-V18, P13-V19
  - Depends on: T13.11
  - Context: 8.4; T4.2 (`InsufficientStock`)
  - Done when: `/ui-review` ran (§0.5); findings fixed or registered.

Checkout error handling: a 409 from `/api/checkout/` renders its per-line errors next to the affected lines ("Solo quedan 2 de …"), and 400 field errors render under their inputs, via `ApiError.fieldErrors`. Per G4's resolution (ADR-0042), "Pagar" also sends `expected_total_cents`, and a 409 with fresh totals re-renders the review section so the customer sees what they will pay.

- [ ] **T13.12 — Purchase-limit message**
  - Release: R1 · Gate: task
  - REQs: REQ-061
  - Verifies: P13-V24
  - Depends on: T13.6
  - Context: T8.8
  - Open items: D15
  - Done when: `/ui-review` ran (§0.5); findings fixed or registered.

A 409 from `/api/checkout/` for a line over its per-customer limit renders the server's per-line message next to that line in the Revisión section, the same way as the stock message (T13.6). No order is created.

- [ ] **T13.4 — Error boundaries**
  - Release: R1 · Gate: task
  - REQs: REQ-053
  - Verifies: P13-V20
  - Depends on: T13.12
  - Context: §4.5 (Composition map)
  - Done when: `/ui-review` ran (§0.5); findings fixed or registered.

A `<NuxtErrorBoundary>` around the cart and checkout regions. A failed API call must show a retry affordance, never a blank page.

- [ ] **T13.7 — Landing pages**
  - Release: R1 · Gate: phase-close
  - REQs: REQ-051, REQ-052
  - Verifies: P13-V13, P13-V14, P13-V15, P13-V16
  - Depends on: T13.4
  - Context: 13.A; 9.6; CR-31
  - Open items: G21, G22 (tests xfail until decided)
  - Done when: `/ui-review` ran (§0.5); findings fixed or registered.

Landing pages:

- `gracias` polls the order status every 2 s for up to 60 s through the order-status endpoint (T13.9). It shows "Confirmando tu pago…" until the order is `paid` or later, then the confirmation. On timeout it shows a message saying the email will confirm.
- `pendiente` shows the voucher link and its expiry prominently, formatted with the store timezone (CR-31).
- `error` offers a retry through the pay-retry endpoint (T13.10) and a link back to the cart.

- [ ] **T13.14 — Pickup and pre-orders in the cart and checkout**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P13-V12, P13-V22, P13-V25
  - Depends on: T13.7; the R2 work of Phases 7, 8 and 10
  - Context: 13.A; 7.5; CR-47
  - Open items: D4, D8
  - Done when: `/ui-review` ran (§0.5); findings fixed or registered.

Pickup and pre-orders in the cart and checkout: the delivery or pickup toggle in Entrega, with the location's address, hours and hold period (D4) and $0.00 shipping; the ship-complete notice for mixed carts with the earliest release date, in the cart and in Revisión; and the logged-in customer's email prefilled in Contacto. How pickup is named and shown follows CR-47 when Release 2 is specified.

#### Verify — test specification

> Every ID below is a named test (§4.6). The phase closes when every in-scope ID passes in `make test-all` (§0.2). ⚠️ G# marks a test written against a gap's proposed resolution, `xfail(strict=True, reason="G#")` until the gap is decided (§2.4). `[R2]` marks an ID outside Release 1; `[manual]` an ID checked by hand in the phase-close report.

**From the original Verify items:**

| Test ID | Layer | File | Assertion |
|---|---|---|---|
| P13-V01 | E2E | `web/e2e/p13_checkout.spec.ts` › `p13_v01 mobile viewport purchase delivery` | On the `mobile` project, a delivery purchase goes through the simulator's "Aprobar con tarjeta" and reaches the confirmed `gracias` view. *The real-device check moves to Phase 22 as `[manual]`; the pickup purchase is P13-V25.* |
| P13-V02 | E2E | `web/e2e/p13_checkout.spec.ts` › `p13_v02 double-click Pagar creates one order` | A `dblclick`, and separately two synthetic clicks fired together, on "Pagar" produce exactly one order for the cart (via `/dev/test/orders/`, T13.8). The button is disabled while the request is in flight, and the browser is redirected once. |

**Composables and components:**

| Test ID | Layer | File | Assertion |
|---|---|---|---|
| P13-V03 | unit | `web/tests/unit/composables/useCart.test.ts` › `p13_v03 state replaced from server response` | After each of `add`, `update`, `remove` and `setFulfillment`, state deep-equals the stubbed server response — including when the server returns a reduced quantity or a different price than requested. With a fixture whose server totals intentionally differ from the sum of its lines, state shows the server totals, which proves nothing is computed client-side. |
| P13-V04 | unit | `web/tests/unit/composables/useCart.test.ts` › `p13_v04 error leaves state untouched` | A 409 or 500 leaves state deep-equal to its prior value — sampled while the request is pending and after it fails — and surfaces an `ApiError`. |
| P13-V05 | component | `web/tests/components/AddressForm.test.ts` › `p13_v05 cp autofill from the fixture` | Typing `06700` fills state and municipality and offers exactly the colonias for 06700 in `api/fixtures/mx_postal_codes_sample.csv`. The test reads that CSV to build the `registerEndpoint` response, so the frontend and backend fixtures cannot drift. Changing the CP clears the chosen colonia. |
| P13-V06 | component | `web/tests/components/AddressForm.test.ts` › `p13_v06 unknown cp falls back to free text` | A 404 for the CP leaves every field editable, shows a message, and still allows submission with a manually chosen state. |
| P13-V07 | component | `web/tests/components/AddressForm.test.ts` › `p13_v07 client and server validation` | Zod rejects a non-5-digit CP and missing required fields; server `fieldErrors` render under the matching inputs. |

**Pages (Playwright, both projects):**

| Test ID | Layer | File | Assertion |
|---|---|---|---|
| P13-V08 | E2E | `web/e2e/p13_cart.spec.ts` › `p13_v08 add to cart updates the badge` | Adding from the product page increments the header badge; `/carrito` shows the line with the server's price. |
| P13-V09 | E2E | `web/e2e/p13_cart.spec.ts` › `p13_v09 quantity above stock shows reduced` | Raising a quantity above `available` shows the server's `reduced` message with `max_available`; the stored quantity is not silently changed. |
| P13-V10 | E2E | `web/e2e/p13_cart.spec.ts` › `p13_v10 remove line and empty state` | Removing the last line shows the empty-cart state with a link to the catalog. |
| P13-V11 | E2E | `web/e2e/p13_checkout.spec.ts` › `p13_v11 delivery quote follows the cp` | CP 06700 and CP 97000 show different quotes (§2.5 dev defaults); a subtotal at or above the free-shipping threshold shows free shipping. |
| P13-V12 [R2] | E2E | `web/e2e/p13_checkout.spec.ts` › `p13_v12 pickup shows store details and zero shipping` | "Recoger en tienda" shows the placeholder store address, hours and hold period, and the shipping line reads $0.00. |
| P13-V13 | E2E | `web/e2e/p13_landing.spec.ts` › `p13_v13 gracias polls until paid` | After approval, `gracias` shows the pending message and then the confirmation once the mock webhook has been processed. ⚠️ G21 |
| P13-V14 | E2E | `web/e2e/p13_landing.spec.ts` › `p13_v14 pendiente shows voucher and expiry` | After "Pagar en OXXO", `pendiente` shows the voucher link (the mock voucher page) and its expiry in es-MX format. ⚠️ G21 |
| P13-V15 | E2E | `web/e2e/p13_landing.spec.ts` › `p13_v15 error page offers retry` | After "Rechazar", `error` offers a retry that leads to a new simulator session for the same order. ⚠️ G22 |
| P13-V16 | a11y | `web/e2e/p13_a11y.spec.ts` › `p13_v16 axe on cart checkout and landing pages` | `expectNoA11yViolations` passes on every 13.A route, on both projects. |

**Added negative and edge cases:**

| Test ID | Layer | File | Assertion |
|---|---|---|---|
| P13-V17 | E2E | `web/e2e/p13_checkout.spec.ts` › `p13_v17 server validation errors inline` | An invalid email, and delivery without an address, show the server's field errors under their inputs; nothing is reserved. |
| P13-V18 | E2E | `web/e2e/p13_checkout.spec.ts` › `p13_v18 stock lost between cart and pay` | A second API client buys the last unit before "Pagar". Checkout shows the per-line 409 message and creates no order. |
| P13-V19 | E2E | `web/e2e/p13_checkout.spec.ts` › `p13_v19 price changed before pay` | The price changes between the review render and "Pagar". "Pagar" gets a 409 `total_changed`, the review section shows the fresh total, and a second press pays that total (G4, ADR-0042). |
| P13-V20 | E2E | `web/e2e/p13_errors.spec.ts` › `p13_v20 cart failure stays inside its boundary` | With the cart API returning 500, the cart region shows "Reintentar" while the header and navigation keep working. |
| P13-V21 | E2E | `web/e2e/p13_checkout.spec.ts` › `p13_v21 idempotency key lifecycle` | Retries after a dropped response resend the same `Idempotency-Key`; reloading the page generates a new one (asserted on intercepted request headers). |
| P13-V22 [R2] | E2E | `web/e2e/p13_checkout.spec.ts` › `p13_v22 mixed cart notice on cart and review` | A cart with a pre-order and an in-stock line shows the ship-complete notice with the release date, both in the cart and in the review section. |

**Added in conversion:**

| Test ID | Layer | File | Assertion |
|---|---|---|---|
| P13-V23 | E2E | `web/e2e/p13_invoice.spec.ts` › `p13_v23 quiero factura fields and errors` | The checkout's "Quiero factura" section shows its fields only when chosen; server field errors render under the matching inputs; the paid order then appears in the admin CFDI queue. |
| P13-V24 | E2E | `web/e2e/p13_checkout.spec.ts` › `p13_v24 purchase limit message` | Exceeding a purchase limit shows the server's per-line message in the review section and creates no order. |
| P13-V25 [R2] | E2E | `web/e2e/p13_checkout.spec.ts` › `p13_v25 mobile viewport purchase pickup` | On the `mobile` project, a pickup purchase goes through the simulator's "Aprobar con tarjeta" and reaches the confirmed `gracias` view. |
| P13-V26 | API | `api/tests/api/orders/test_status_token.py::test_p13_v26_status_token` | A valid order-status token returns the order's status; an expired or tampered token returns 404 with the same body as a missing order. ⚠️ G21 |
| P13-V27 | API | `api/tests/api/orders/test_pay_retry.py::test_p13_v27_pay_retry` | `POST /api/orders/{public_id}/pay/` returns a fresh `checkout_url` while the order is `pending_payment`, without new reservations, and 409 in any other state. ⚠️ G22 |

**Fixtures and factories introduced** (reused by later phases)

- `cartResponse(overrides)` — a typed cart payload builder for `useCart` tests
- `postalFixture(cp)` — builds the `/api/postal-codes/{cp}/` response from the committed sample CSV
- Playwright `checkoutAs(page, { email, cp, invoice? })` and `payInSimulator(page, button)` helpers (`fulfillment` is an R2 option)
- Playwright `inspect.inventory(sku)` and `inspect.orders(email)` — wrappers around the T13.8 endpoints
- `status_token(order)` — issues an order-status token for API tests

### Phase 14 — Frontend account pages

**Deliverable:** Release 1: guest order lookup at `/rastrear`, wired to the 6.7 API. Release 2: registration with email verification, login, logout, password reset, the account area with order history, order detail and saved addresses — all wired to the Phase 6 API.

**Release 1 scope:** `/rastrear` only (T14.6); every other task is R2.

#### 14.A Pages

| Route | File | Notes | Release |
|---|---|---|---|
| `/mi-cuenta` | `pages/mi-cuenta/index.vue` | | R2 |
| `/mi-cuenta/pedidos` | | Order history | R2 |
| `/mi-cuenta/pedidos/[id]` | | Order detail with timeline | R2 |
| `/mi-cuenta/direcciones` | | Address CRUD | R2 |
| `/entrar`, `/registro`, `/recuperar` | | Auth | R2 |
| `/verificar` | `pages/verificar.vue` | Target of the verification email link; reads `?token=` | R2 |
| `/recuperar/nueva` | `pages/recuperar/nueva.vue` | Target of the reset email link; sets the new password | R2 |
| `/rastrear` | | Guest order lookup (number + email) | R1 |

#### Tasks

- [ ] **T14.6 — Guest order lookup page**
  - Release: R1 · Gate: phase-close
  - REQs: REQ-051
  - Verifies: P14-V09, P14-V17
  - Depends on: Phase 13 closed
  - Context: 14.A; §4.5 (Consumption rules, Composition map); 6.7
  - Open items: —
  - Done when: `/ui-review` ran (§0.5); findings fixed or registered.

`/rastrear` calls the guest lookup endpoint (6.7): `POST` with a JSON body (G35, ADR-0040). A wrong email and a missing order show the same message. The form is built from DS parts with `UForm` and Zod (CR-28), and submits through `useApi`. The result shows the order's status as a DS badge with its Spanish label; the full timeline is R2 (DSR-08).

- [ ] **T14.1 — Account route guard**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P14-V03
  - Depends on: T14.6
  - Context: 14.A; 12.3

`middleware/auth.ts` — route guard for `/mi-cuenta/*`.

- [ ] **T14.2 — Order timeline component**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P14-V02
  - Depends on: T14.1, DSR-08 released
  - Context: §4.5 (Composition map)
  - Open items: DSR-08 (blocking)

Account components, built from DS parts (CR-26): `OrderTimeline` (DSR-08). `AddressForm` from 13.2 is reused on the addresses page.

- [ ] **T14.3a — Login, logout and the guard redirect**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P14-V01, P14-V06, P14-V11, P14-V13
  - Depends on: T14.1
  - Context: 14.A; 7.2; 12.3

Login and logout pages. Forms use `UForm` and Zod and submit through `useApi`.

- The guard redirects to `/entrar?next=<path>`, and a successful login returns there.
- After login, the cart is re-fetched so the server-side merge (7.2) is visible immediately.
- Logout clears `useAuth` state and re-fetches the cart.

- [ ] **T14.3b — Registration, verification, password reset and claiming**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P14-V04, P14-V05, P14-V12, P14-V14
  - Depends on: T14.3a
  - Context: 14.A; 6.1, 6.8

Registration (`/registro`), email verification (`/verificar`), password reset (`/recuperar`, `/recuperar/nueva`), and the offer to claim guest orders after verification (6.8). Forms use `UForm` and Zod and submit through `useApi`.

- [ ] **T14.4 — Order history and detail**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P14-V07, P14-V15
  - Depends on: T14.2, T14.3a
  - Context: 14.A; 6.7

Order history and detail. The list is paginated from `GET /api/orders/`. Detail renders `OrderTimeline` from the order's events, the shipment's tracking link, and the voucher if one is pending.

- [ ] **T14.5 — Saved addresses**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P14-V08, P14-V10, P14-V16
  - Depends on: T14.4
  - Context: 14.A; 6.5

Addresses page: create, edit, delete and make default, with the server's 10-address cap surfaced as a message. This is the last account page, so it also adds the axe spec for the account routes (P14-V10).

#### Verify — test specification

> Every ID below is a named test (§4.6). The phase closes when every in-scope ID passes in `make test-all` (§0.2). ⚠️ G# marks a test written against a gap's proposed resolution, `xfail(strict=True, reason="G#")` until the gap is decided (§2.4). `[R2]` marks an ID outside Release 1; `[manual]` an ID checked by hand in the phase-close report.

**From the original Verify items:**

| Test ID | Layer | File | Assertion |
|---|---|---|---|
| P14-V01 [R2] | E2E | `web/e2e/p14_auth.spec.ts` › `p14_v01 anonymous cart survives login` | Two lines added anonymously are still in the cart after logging in; the seeded customer's existing line is merged per 7.2 and the badge shows the merged count. |

**Components and middleware:**

| Test ID | Layer | File | Assertion |
|---|---|---|---|
| P14-V02 [R2] | component | `web/tests/components/OrderTimeline.test.ts` › `p14_v02 events in order with Spanish labels` | Events render oldest to newest. An exhaustive check asserts that every one of the 14 order states has a Spanish label, so a new state without a label fails. |
| P14-V03 [R2] | unit | `web/tests/unit/middleware/auth.test.ts` › `p14_v03 guard redirects anonymous visitors` | With `me = null`, `/mi-cuenta/pedidos` redirects to `/entrar?next=%2Fmi-cuenta%2Fpedidos`; with a customer it passes through. |

**Pages (Playwright, both projects):**

| Test ID | Layer | File | Assertion |
|---|---|---|---|
| P14-V04 [R2] | E2E | `web/e2e/p14_auth.spec.ts` › `p14_v04 register verify login logout` | Register, then open the verification link from the newest file in `var/emails/` (`readLatestEmail`). `/verificar` confirms; log in; the header shows the name; logout clears it and resets the cart badge. |
| P14-V05 [R2] | E2E | `web/e2e/p14_auth.spec.ts` › `p14_v05 password reset flow` | Request a reset, open the emailed link to `/recuperar/nueva`, set a new password; the old password fails and the new one succeeds. |
| P14-V06 [R2] | E2E | `web/e2e/p14_guard.spec.ts` › `p14_v06 account routes redirect and return` | An anonymous visit to `/mi-cuenta/direcciones` lands on `/entrar`; logging in returns to `/mi-cuenta/direcciones`. |
| P14-V07 [R2] | E2E | `web/e2e/p14_orders.spec.ts` › `p14_v07 order history and detail timeline` | The seeded customer's orders are listed newest first; the delivered order's detail shows its timeline and tracking link; the pending OXXO order shows its voucher. |
| P14-V08 [R2] | E2E | `web/e2e/p14_addresses.spec.ts` › `p14_v08 address crud and default toggle` | Create, edit and delete an address; making another address the default leaves exactly one default badge. |
| P14-V09 | E2E | `web/e2e/p14_tracking.spec.ts` › `p14_v09 guest tracking lookup` | The right number and email show the order status; a wrong email shows the same "no encontramos ese pedido" message as a nonexistent number. |
| P14-V10 [R2] | a11y | `web/e2e/p14_a11y.spec.ts` › `p14_v10 axe on auth and account pages` | `expectNoA11yViolations` passes on every R2 route of 14.A (the account and auth pages), on both projects. |

**Added negative and edge cases:**

| Test ID | Layer | File | Assertion |
|---|---|---|---|
| P14-V11 [R2] | E2E | `web/e2e/p14_auth.spec.ts` › `p14_v11 lockout message after five failures` | After 5 wrong passwords, a Spanish lockout message appears, and it doesn't reveal whether the account exists. |
| P14-V12 [R2] | E2E | `web/e2e/p14_auth.spec.ts` › `p14_v12 reset for unknown email looks identical` | Requesting a reset for an unknown email shows the same confirmation as for a known one, and no email file is written. |
| P14-V13 [R2] | E2E | `web/e2e/p14_auth.spec.ts` › `p14_v13 expired session mid-visit` | After the session cookie is cleared, the next account navigation redirects to `/entrar?next=…`, while the cart keeps working anonymously. |
| P14-V14 [R2] | E2E | `web/e2e/p14_auth.spec.ts` › `p14_v14 claim guest orders after verification` | A guest order placed with an email, followed by registering and verifying that email, offers to claim it; after claiming, it appears in `/mi-cuenta/pedidos`. |
| P14-V15 [R2] | E2E | `web/e2e/p14_orders.spec.ts` › `p14_v15 another customer's order shows not found` | Opening another customer's order URL shows the not-found page, never that order's data. |
| P14-V16 [R2] | E2E | `web/e2e/p14_addresses.spec.ts` › `p14_v16 address cap message` | Adding an 11th address shows the server's cap message, and the list still has 10. |

**Added in conversion:**

| Test ID | Layer | File | Assertion |
|---|---|---|---|
| P14-V17 | a11y | `web/e2e/p14_tracking.spec.ts` › `p14_v17 axe on rastrear` | `expectNoA11yViolations` passes on `/rastrear` — empty, showing a found order, and showing the not-found message — on both projects. |

**Fixtures and factories introduced** (reused by later phases)

- Playwright `loginAs(page, who)` `[R2]` — logs in as a seeded customer (from the `seed` manifest); in R1, staff sign in through `adminLogin` (15.4)
- Playwright `readLatestEmail(to)` — reads the newest file for that recipient from the bind-mounted `var/emails/` (written by `FileEmailSender`, §4.3)

### Phase 15 — Local acceptance

Local acceptance is the complete Release 1 store — catalog, cart, guest checkout, payments, delivery, manual CFDI, the pre-launch mode, transactional email and the admin back office — running entirely on one developer machine with `docker compose up`. Every third-party service is replaced by its mock (§4.3): payments by the local simulator, the carrier by the mock tracking page, email by files on disk, media by the local filesystem, postal codes by the committed sample. Nothing leaves the machine. The code downstream of each adapter is exactly the code that will run in production, so local acceptance proves the business logic end to end; Part B only swaps adapters and deploys. Pickup, pre-orders, counter sales and customer accounts join in Release 2 (§1.2).

It is accepted when the Release 1 journeys below pass on both Playwright projects, the demo script can be followed without deviation, and `make test-all` passes from a clean clone with no network access beyond package installs.

**Deliverable:** a seeded demo dataset, a written demo script, the Release 1 journeys, and an offline clean-clone run that proves the exit criterion.

**Release 1 scope:** journeys J1, J3, J4, J8, J10 and J11; the demo; the offline proof. J2, J5, J6, J7 and J9 are R2.

#### 15.A Demo dataset

Everything is fictional and labelled: product names start with `[DEMO]`, the franchise is "Franquicia Demo", and every email uses the reserved `.test` domain. Placeholder business values come from §2.5.

| Item | Contents | Used by |
|---|---|---|
| Warehouse and shipping | The §2.5 dev defaults: the `[PLACEHOLDER]` warehouse `almacen` (not a pickup point, never shown as a store, CR-47), zones `local` (CMX + MEX) and `nacional`, free shipping from MXN 1,500 | All journeys |
| Product types | The 5 launch types (D14 stand-in), plus **`artbook`**, created only as data (`ilustrador`, `paginas`, `idioma`, `pasta_dura`), to show a new category with zero code changes | Demo step 2, P12-V11 in spirit |
| `[DEMO] Caja de sobres TCG` | `tcg_sealed`, MXN 2,499.00, `on_hand` 3 | J1, J8 |
| `[DEMO] Fundas para cartas` | `accessory`, MXN 199.00, `on_hand` 20 | Demo step 1 |
| `[DEMO] Sudadera` | `apparel`, MXN 749.00; 6 variants S/M/L × negro/blanco; S/negro `on_hand` 0, M/negro 2, the rest 5 | Demo step 3; J6 `[R2]` |
| `[DEMO] Playera` | `apparel`, MXN 349.00; 3 sizes, `on_hand` 10 each | J10, J11; J2, J7 `[R2]` |
| `[DEMO] Figura` | `figure`, MXN 1,299.00, `on_hand` 4 | J3, J4 |
| `[DEMO] Artbook` | `artbook`, MXN 999.00, `on_hand` 2 | Demo step 2 |
| Hidden products | One `draft`, one `archived` | P12-V23 |
| Guest order history | Guest orders under `demo@cupnoobles.test`: 1 `completed` delivery, 1 `pending_payment` OXXO with an active voucher, 1 `paid` delivery with a CFDI `requested` | Demo steps 9 and 13; P14-V09 |
| Staff | `staff@cupnoobles.test`, superuser | Demo steps 6–10; J1, J10, J11 |
| Passwords | A fixed dev password, printed by `make demo`; valid only where `DEV_TOOLS_ENABLED` | — |
| `[DEMO] Juego de mesa` `[R2]` | `board_game`, MXN 899.00, `on_hand` **1** — the last unit | J9 `[R2]` |
| `[DEMO] Figura preventa` `[R2]` | `figure`, MXN 1,899.00, pre-order, `preorder_limit` 5, release date seed day + 30, `on_hand` 0 | J5, J6 `[R2]` |
| Customer account `[R2]` | `demo@cupnoobles.test`, verified. Addresses: CP 06700 (default) and CP 97000. A saved cart with 1 `[DEMO] Playera`. Order history: 1 `completed` delivery, 1 `awaiting_stock` pre-order, 1 `pending_payment` OXXO with an active voucher | J2, J7, P14-V07 `[R2]` |

#### 15.B Demo script

`docs/demo-script.md` is written for the developer to walk the store owner through local acceptance in about 15 minutes. Every step names the Spanish UI label to click and the result to expect. Start with `make demo`.

| # | Where | Do | Expect |
|---|---|---|---|
| 1 | Storefront `/` | Browse the home page and open "Catálogo". | Featured products (G28); the facet sidebar shows filters for each product type. |
| 2 | `/producto/<artbook>` | Open `[DEMO] Artbook`. | A correct spec table for a category added as data only — the attribute-agnostic model in action. |
| 3 | `/producto/<sudadera>` | Select talla S, color negro, then M/negro. | S/negro shows "Agotado"; M/negro shows "Últimas piezas" and can be added. |
| 4 | `/checkout` | As a guest, add the TCG box, enter CP 06700, then "Pagar" → "Aprobar con tarjeta". | Free shipping (above the threshold), the simulator banner, then "¡Gracias!" once confirmed. |
| 5 | `var/emails/` | Open the newest `order_confirmation` file. | The Spanish confirmation with the order number. |
| 6 | `/admin/` | Log in as staff, open the order, add a shipment leaving the tracking number blank. | `MOCK-<number>-1`, order `shipped`, a tracking email file. |
| 7 | Mock tracking page | Press "Entregado". | The order is `delivered` in the admin timeline. |
| 8 | Storefront | Buy `[DEMO] Figura` choosing "Pagar en OXXO"; on the voucher page press "Simular pago recibido". | `pendiente` shows the ficha; after payment the order is `paid`. |
| 9 | Admin CFDI queue | Open the seeded order with a CFDI `requested`; record a folio, a UUID and the two sample documents. | The request is `issued`; a `cfdi_issued` email file with the PDF and XML attached. |
| 10 | Admin + a private window | Turn pre-launch mode on; open the storefront in a private window; then turn the mode off. | The private window shows "próximamente" while the staff session still sees the catalog; after switching off, the private window shows the catalog. |
| 11 `[R2]` | Storefront + admin | Pre-order `[DEMO] Figura preventa`, then in the admin receive 1 unit for it. | The order moves `awaiting_stock` → `preparing` with a "ya llegó" email. |
| 12 `[R2]` | Admin "Registrar venta en tienda" | Sell the last `[DEMO] Juego de mesa` at the counter. | Reloading its product page shows "Agotado". |
| 13 | `/rastrear` | Look up the seeded OXXO order with its number and `demo@cupnoobles.test`. | Its status and voucher link. In R2, logging in as `demo@cupnoobles.test` shows the history and merges the saved cart. |
| 14 | Terminal | `make demo-reset`. | A clean dataset, ready for the next run. |

#### 15.C Journeys

Every journey runs against `docker compose up` with every provider set to its mock, on both the `desktop` and `mobile` projects, with the offline guard active and `expectNoA11yViolations` on every page visited. Stock and order effects are asserted with `inspect.*` (13.8); emails with `readLatestEmail`. The journeys are the first table of the Verify specification below.

#### Exit criterion

**`make test-all` passes from a clean clone with no network access beyond package installs** — proven by P15-V14, reproducible locally with `make clean-clone-check`. When it passes, Part A is complete and Part B may begin.

#### Tasks

- [ ] **T15.1 — Demo dataset**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: [no-test: P15-V10 (T15.7) checks the dataset against the demo script; P15-V11 (T15.3) checks the production guard]
  - Depends on: Phase 14 closed
  - Context: 15.A; §2.5; 3.7

`manage.py seed_demo [--reset]` — replaces the minimal seed from 3.7 with the dataset in 15.A (its R1 rows; the R2 rows arrive with their features).

- Deterministic: the same ids, slugs, SKUs and prices on every run.
- Built through services (`create_product`, `receive_stock`, `order_in_state`), never raw inserts, so it cannot create states the system couldn't reach.
- `--reset` flushes application tables and the mock stores (`MOCK_STORE_DIR`, `EMAIL_FILE_DIR`, `MEDIA_ROOT`), then reseeds.
- Refuses to run unless `DEV_TOOLS_ENABLED`.

- [ ] **T15.2 — End-to-end dataset**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: [no-test: used by every journey; the production guard is P15-V11 (T15.3)]
  - Depends on: T15.1
  - Context: 15.A; §4.6 (E2E)

`manage.py seed_e2e` — `seed_demo` plus data owned by individual specs: variants with SKU prefix `E2E-<spec>` for every spec that mutates stock (§4.6). It writes `var/e2e/manifest.json` (slugs, SKUs, emails, passwords, order numbers) for the Playwright `seed` fixture.

- [ ] **T15.3 — Dev command runner**
  - Release: R1 · Gate: task
  - REQs: REQ-040
  - Verifies: P15-V11
  - Depends on: T15.2
  - Context: §4.3 (dev tools), §4.8

Dev command runner `POST /dev/test/run/` — runs one whitelisted management command with arguments: `expire_reservations`, `advance_orders`, `reconcile_payments`, `sync_shipments`, `mock_payments expire-order`, `mock_payments deliver --once`. Registered only when `DEV_TOOLS_ENABLED` (404 in production). Journeys use it to move the clock-driven jobs forward on demand instead of waiting for the scheduler.

- [ ] **T15.4 — End-to-end helpers**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: [no-test: exercised by the journeys (T15.6a, T15.6b)]
  - Depends on: T15.3
  - Context: §4.6 (E2E)

E2E helpers in `web/e2e/fixtures.ts`:

- `run(command, args)` — calls 15.3
- `adminLogin(page)` — the seeded staff user
- `inspect.*` from 13.8 and `readLatestEmail` from Phase 14 are reused

- [ ] **T15.6a — Journeys J1, J3 and J4**
  - Release: R1 · Gate: task
  - REQs: REQ-012, REQ-051
  - Verifies: P15-V01, P15-V03, P15-V04
  - Depends on: T15.4
  - Context: 15.C; 9.4; 13.7

The journey specs for J1, J3 and J4 in `web/e2e/journeys/` (15.C). Each runs on both projects, calls `expectNoA11yViolations` on every page it visits, and uses the offline guard.

- [ ] **T15.6b — Journeys J8, J10 and J11**
  - Release: R1 · Gate: task
  - REQs: REQ-010, REQ-021, REQ-051, REQ-060, REQ-062
  - Verifies: P15-V08, P15-V15, P15-V16
  - Depends on: T15.6a
  - Context: 15.C; 8.4; §3.7
  - Open items: —

The journey specs for J8 (double-click "Pagar"), J10 (CFDI) and J11 (pre-launch), on the same terms as T15.6a. J10 uses the sample CFDI documents in `web/e2e/fixtures/`.

- [ ] **T15.7 — Demo script and make targets**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P15-V10
  - Depends on: T15.6b
  - Context: 15.B; §0.3

`docs/demo-script.md` (15.B), plus `make demo`, which runs `docker compose up`, then `seed_demo --reset`, then prints the URLs and demo credentials; and `make demo-reset`.

- [ ] **T15.8 — Demo rows fail the placeholder check**
  - Release: R1 · Gate: task
  - REQs: REQ-065
  - Verifies: P15-V12
  - Depends on: T15.7
  - Context: §2.5; T2.9

Add `[DEMO]` to the markers `check_placeholders` rejects (§2.5; the command is built in T2.9), so demo data can never reach production unnoticed.

- [ ] **T15.5 — Offline execution**
  - Release: R1 · Gate: phase-close
  - REQs: REQ-042, REQ-073
  - Verifies: P15-V13, P15-V14
  - Depends on: T15.8
  - Context: §0.3; §4.5 (Offline); §4.6 (E2E)
  - Done when: the CI job `clean-clone-offline` is green on `main`.

Offline execution:

- An `e2e` service in `docker-compose.e2e.yml` runs Playwright from the official Playwright image, pinned to the project's `@playwright/test` version, with browsers baked into the image.
- `docker-compose.offline.yml` declares the project network `internal: true`, so no container — API, web, proxy or `e2e` — can reach the internet.
- `make test-all-offline` builds every image first (package installs, including the DS packages from GitHub Packages with the `NODE_AUTH_TOKEN` build secret, are the only network step), then runs `make test-all` under the offline override.
- A CI job, `clean-clone-offline`, does the same from a fresh checkout.
- `make clean-clone-check` reproduces it locally by cloning into a temporary directory.

- [ ] **T15.6c — Journeys J2, J5, J6, J7 and J9**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P15-V02, P15-V05, P15-V06, P15-V07, P15-V09
  - Depends on: T15.5
  - Context: 15.C; 10.A

The Release 2 journey specs (pickup, pre-orders, mixed carts, cart merge on login, counter sales), on the same terms as T15.6a.

#### Verify — test specification

> Every ID below is a named test (§4.6). The phase closes when every in-scope ID passes in `make test-all` (§0.2). ⚠️ G# marks a test written against a gap's proposed resolution, `xfail(strict=True, reason="G#")` until the gap is decided (§2.4). `[R2]` marks an ID outside Release 1; `[manual]` an ID checked by hand in the phase-close report.

**From the original Verify items (the journeys):**

| Test ID | Layer | File | Assertion |
|---|---|---|---|
| P15-V01 | E2E journey | `web/e2e/journeys/j1_guest_card_delivery.spec.ts` › `p15_v01 guest card purchase with delivery` | As a guest: product → cart → checkout with CP 06700 (autofilled) → "Pagar" → "Aprobar con tarjeta" → `gracias` confirmed. `inspect`: order `preparing`, `on_hand` −1, `reserved` back to 0. An `order_confirmation` email exists. Staff add a blank-tracking shipment → `shipped` with `MOCK-<number>-1` and a tracking email; "Entregado" on the tracking page → `delivered`; `/rastrear` with number + email shows it as delivered. |
| P15-V02 [R2] | E2E journey | `web/e2e/journeys/j2_logged_in_pickup.spec.ts` › `p15_v02 logged-in pickup purchase` | Log in as the demo customer; checkout prefills the email; "Recoger en tienda" shows the store and $0.00 shipping; pay by card → `ready_for_pickup` with `pickup_deadline_at` set and a "listo para recoger" email; staff press "Entregado" → `picked_up`; `/mi-cuenta/pedidos` shows the order as collected. |
| P15-V03 | E2E journey | `web/e2e/journeys/j3_oxxo_paid.spec.ts` › `p15_v03 oxxo pending then paid` | "Pagar en OXXO" → `pendiente` with the voucher and its expiry, and an `oxxo_voucher` email. `inspect`: `reserved` +1, `on_hand` unchanged. The voucher page's "Simular pago recibido" → the order is `paid`; `reserved` back to 0; `on_hand` −1. |
| P15-V04 | E2E journey | `web/e2e/journeys/j4_oxxo_expired.spec.ts` › `p15_v04 oxxo expired releases stock` | "Pagar en OXXO", then "Simular vencimiento": the order stays `pending_payment` (9.4 maps `cancelled` to no event). `run("mock_payments expire-order")` → `expired`; `reserved` back to 0 and `on_hand` unchanged; an `order_expired` email; the product page shows the original availability again. |
| P15-V05 [R2] | E2E journey | `web/e2e/journeys/j5_preorder_to_shipped.spec.ts` › `p15_v05 preorder received allocated shipped` | Buy the pre-order figure → `awaiting_stock`; `preorder_committed` +1 and `stock_item` unchanged. Staff receive 1 unit in the admin → the order is allocated → `preparing` with a "ya llegó" email. Staff add a shipment → `shipped`. |
| P15-V06 [R2] | E2E journey | `web/e2e/journeys/j6_mixed_cart.spec.ts` › `p15_v06 mixed cart ships complete` | Cart with M/negro + the pre-order figure shows the ship-complete notice; pay → `awaiting_stock`; the in-stock line is already committed (`on_hand` −1); the admin action bar offers no shipment. After receiving the pre-order unit → `preparing`, and exactly one shipment → `shipped`. |
| P15-V07 [R2] | E2E journey | `web/e2e/journeys/j7_cart_survives_login.spec.ts` › `p15_v07 anonymous cart survives login` | Two lines added anonymously; log in as the demo customer; the cart holds both, plus the saved `[DEMO] Playera`, summed and clamped per 7.2; checkout proceeds from the merged cart. |
| P15-V08 | E2E journey | `web/e2e/journeys/j8_double_click_pay.spec.ts` › `p15_v08 double-click Pagar creates one order` | Under network throttling (to widen the race window), `dblclick` on "Pagar": `inspect.orders` shows exactly one order for the email, `reserved` rises by the cart quantity once, and the browser reaches the simulator once. |
| P15-V09 [R2] | E2E journey | `web/e2e/journeys/j9_counter_sale.spec.ts` › `p15_v09 counter sale updates storefront availability` | The last `[DEMO] Juego de mesa` shows "Últimas piezas". Staff record a counter sale of 1 in "Registrar venta en tienda". A full reload of the product page shows "Agotado"; a second tab that still shows the old badge gets the server's rejection on add-to-cart; the admin ledger shows `sale_in_store`. A client-side badge may lag by up to 60 s (5.6); the test asserts on a full load. |

**Added checks for local acceptance as a whole:**

| Test ID | Layer | File | Assertion |
|---|---|---|---|
| P15-V10 | integration | `api/tests/integration/demo/test_demo_script.py::test_p15_v10_demo_script_matches_seed` | After `seed_demo`, every SKU, slug, email and product name mentioned in the R1 steps of `docs/demo-script.md` exists with the stated stock, and `seed_demo` run twice produces identical data. |
| P15-V11 | integration | `api/tests/integration/demo/test_seed_guards.py::test_p15_v11_seed_and_runner_refuse_in_prod` | Under `prod.py`, `seed_demo` and `seed_e2e` raise `CommandError`, and `/dev/test/run/` and `/dev/test/inventory/…` return 404; the runner rejects commands not on its whitelist. |
| P15-V12 | integration | `api/tests/integration/demo/test_check_placeholders.py::test_p15_v12_demo_rows_fail_placeholder_check` | `check_placeholders` exits non-zero while any `[DEMO]` row exists. |
| P15-V13 | E2E | `web/e2e/p15_offline.spec.ts` › `p15_v13 internal network blocks egress` | From inside the `e2e` container, a Node `fetch("https://example.com")` fails at the network level. This proves isolation independently of the Playwright guard. |
| P15-V14 | CI | `.github/workflows/ci.yml` job `clean-clone-offline` › `p15_v14 clean clone passes test-all offline` | A fresh checkout builds every image, then `make test-all-offline` exits 0 with the project network internal. **This is the local acceptance exit criterion.** |

**Added in conversion:**

| Test ID | Layer | File | Assertion |
|---|---|---|---|
| P15-V15 | E2E journey | `web/e2e/journeys/j10_cfdi_request.spec.ts` › `p15_v15 cfdi requested issued and emailed` | J10: as a guest, `[DEMO] Playera` → checkout with "Quiero factura" and valid sample fiscal data → pay by card → `gracias` confirmed. Staff open the admin CFDI queue, record a folio, a UUID and the sample PDF and XML: the request is `issued`, and a `cfdi_issued` email exists with both attachments (`readLatestEmail`). |
| P15-V16 | E2E journey | `web/e2e/journeys/j11_prelaunch.spec.ts` › `p15_v16 prelaunch hides catalog until go-live` | J11: with pre-launch mode on, an anonymous visitor sees "próximamente"; staff log in, buy `[DEMO] Playera` through the simulator and refund the order; staff publish the catalog and turn the mode off; the anonymous visitor now sees the catalog. |

**Fixtures and factories introduced:**

- `seed_demo`, `seed_e2e` and the `var/e2e/manifest.json` contract
- Playwright `run(command, args)` and `adminLogin(page)`; journey specs reuse every earlier helper
- `web/e2e/fixtures/cfdi-sample.pdf` and `cfdi-sample.xml` — sample documents for J10 and demo step 9; not real CFDI

Part B — Production (Phases 16–22). Real integrations, deployment, observability and the Release 1 launch. Part B starts only after P15-V14 passes. Most Part B checks need real accounts or the live site, so many of their Verify IDs are `[manual]`; everything that can run offline is automated.

### Phase 16 — Mercado Pago integration

**Part B — Production.** Phases 16 to 22 add the real integrations, deployment, observability and launch. Part B starts only after local acceptance (P15-V14).

**Deliverable:** `MercadoPagoProvider` in `apps/payments/mercadopago.py` implements the `PaymentProvider` interface from 9.1 and is selected with `PAYMENT_PROVIDER=mercadopago` (§4.3). No code outside the adapter changes. Requires S2.

**Acceptance criterion:** the payment contract suite from 9.13 — the same scenarios Part A runs against the mock — passes with `PAYMENT_PROVIDER=mercadopago` against the Mercado Pago sandbox (P16-V01).

**Release 1 scope:** all tasks.

#### Tasks

- [ ] **T16.1 — Account and credentials**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: [no-test: account setup by the owner; the credentials are exercised by P16-V01]
  - Depends on: Phase 15 closed, S2
  - Context: §4.7 (Real-provider credentials); CR-50
  - Open items: S2 (blocking)
  - Done when: the test credentials, the webhook secret and the sandbox test users exist, stored only as secrets; the steps are recorded in `RUNBOOK.md`.

Account and credentials (S2). The agent lists the steps; the owner performs them in the Mercado Pago dashboard (§0.1 step 12):

- Create the Mercado Pago application and obtain **test** credentials, `MP_ACCESS_TOKEN` and `MP_PUBLIC_KEY`.
- Configure webhooks for the `payment` topic and store the signing secret as `MP_WEBHOOK_SECRET`.
- Create the sandbox test users (buyer and seller) that Mercado Pago's documentation requires.
- Production credentials are swapped in at launch (Phase 22), never before.

- [ ] **T16.2 — Checkout preference**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P16-V04
  - Depends on: T16.1
  - Context: 9.1, 9.2, 9.5; §4.3; §4.7
  - Open items: D6, D7 (stand-in §2.5; decided before the phase closes)

`create_checkout` builds a Checkout Pro preference:

- `items` from `order_line`: name, quantity, and `unit_price` in pesos via `cents_to_pesos` (9.2). Mercado Pago wants pesos; the database holds centavos.
- `external_reference = order.public_id`
- `notification_url = https://<domain>/api/webhooks/payments/mercadopago/`
- `back_urls` → `/pedido/{public_id}/gracias`, `/pedido/{public_id}/pendiente`, `/pedido/{public_id}/error` (with the order-status token if G21 is decided that way)
- `payment_methods.installments` per D7 (`PAYMENT_INSTALLMENT_OPTIONS`)
- `expires = true`, `expiration_date_to = order.payment_deadline_at`

- [ ] **T16.3 — Fetching payments and status mapping**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P16-V05
  - Depends on: T16.2
  - Context: 9.1, 9.4

`fetch_payment` and `find_payments`, the latter searching payments by `external_reference`, and `cancel_payment` (T9.15), which sets a pending payment to cancelled. Map Mercado Pago's vocabulary into `NormalizedStatus`:

| MP `status` | MP `status_detail` | `NormalizedStatus` |
|---|---|---|
| `approved` | `accredited` | `approved` |
| `pending` | `pending_waiting_payment` | `pending` — read the voucher URL and expiry from the payment |
| `in_process` | any | `in_review` |
| `rejected` | any | `rejected` |
| `cancelled` | any | `cancelled` |
| `refunded` | — | `refunded` |
| `charged_back` | — | `charged_back` |
| any, with a refunded amount below the transaction amount | — | `partially_refunded` |

Confirm the field names for the voucher, the expiry and refunded amounts against current Mercado Pago documentation, and pin them with fixtures of real sandbox responses.

- [ ] **T16.4 — Webhook signature verification**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P16-V06
  - Depends on: T16.3
  - Context: 9.A, 9.2, 9.3

`verify_webhook` with Mercado Pago's `x-signature` / `x-request-id` scheme through `signing.verify` (9.2). Confirm two things against current Mercado Pago documentation: the exact signed manifest, and which notification field is a stable delivery id for `webhook_event.external_id` (9.A rule 4). If no stable delivery id exists, use `x-request-id`. Add captured sandbox notifications as unit-test fixtures.

- [ ] **T16.5 — Refunds**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P16-V07
  - Depends on: T16.4
  - Context: 9.8
  - Open items: G45 (blocking)

`refund` through Mercado Pago's refunds API. Raise `RefundNotSupported` for payment methods Mercado Pago cannot refund (cash), so the 9.8 admin warning appears exactly as it does with the mock.

- [ ] **T16.6 — Sandbox reachability**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P16-V02
  - Depends on: T16.5
  - Context: §0.3 (`make test-sandbox`); §4.6

Webhook reachability for sandbox testing: expose the dev server through a tunnel (`cloudflared tunnel --url http://localhost:8080` or ngrok) and register `https://<tunnel>/api/webhooks/payments/mercadopago/` in the Mercado Pago test application. Sandbox tests are the only tests allowed network access. Mark them `@pytest.mark.sandbox`, exclude them from `make test` and `make test-all`, and run them with `make test-sandbox` without `--disable-socket`.

Tests that import a vendor SDK carry the `integrations` marker and run in `make test-integrations`, which installs the `integrations` dependency group and keeps sockets disabled (§0.3, CR-23); CI runs it as the `test-integrations` job from this phase on. Only the sandbox contract run (P16-V01) carries `sandbox` and needs the network. They import the adapter inside the test function, so `pytest --collect-only` still lists them for traceability (§4.6) in an environment without the group.

- [ ] **T16.7 — Sandbox contract driver**
  - Release: R1 · Gate: phase-close
  - REQs: REQ-041
  - Verifies: P16-V01, P16-V03 [manual]
  - Depends on: T16.6
  - Context: 9.13; §4.6
  - Done when: the phase-close report includes the `make test-sandbox` output and every skip reason is recorded in `RUNBOOK.md`.

`MercadoPagoSandboxDriver` for the 9.13 suite:

- Create checkouts through the adapter.
- Complete card outcomes using Mercado Pago's documented test cards and test-user flow.
- Wait for real notifications arriving through the tunnel.
- Where the sandbox cannot drive a scenario — completing an OXXO cash payment, for example, may not be possible — `supports()` returns the reason. The scenario is skipped with that reason, which is also recorded in `RUNBOOK.md`.

Scenarios that don't depend on how a payment is completed still run: PAY-09 to PAY-12 and PAY-19, via the `webhooks …` commands (9.12) against captured Mercado Pago notifications.

#### Verify — test specification

> Every ID below is a named test (§4.6). The phase closes when every in-scope ID passes in `make test-all` (§0.2). ⚠️ G# marks a test written against a gap's proposed resolution, `xfail(strict=True, reason="G#")` until the gap is decided (§2.4). `[R2]` marks an ID outside Release 1; `[manual]` an ID checked by hand in the phase-close report.

In this phase, P16-V01 passes in `make test-sandbox`, and the IDs whose layer says `integrations` pass in `make test-integrations`; the phase-close report carries both runs' output. The Part A suite keeps passing unchanged with `PAYMENT_PROVIDER=mock` in `make test-all` (P9-V01).

**From the plan's checklist:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P16-V01 | contract (`sandbox`, network) | `api/tests/contract/payments/test_sandbox_suite.py::test_p16_v01_sandbox_suite` | With `PAYMENT_PROVIDER=mercadopago`, every scenario PAY-01 to PAY-19 either passes against the sandbox or is skipped with the reason returned by `MercadoPagoSandboxDriver.supports()`. Zero failures; no scenario is skipped without a recorded sandbox limitation. |
| P16-V02 | unit (`integrations`) | `api/tests/unit/payments/test_mercadopago_settings.py::test_p16_v02_prod_starts_with_mercadopago` | A subprocess running `django.setup()` with `config.settings.prod`, `PAYMENT_PROVIDER=mercadopago` and dummy credentials starts, and `providers.payment_provider().code == "mercadopago"`. (Refusing `mock` is P1-V14.) |
| P16-V03 [manual] | manual | Phase-close report | One sandbox purchase in a browser through the real Checkout Pro UI, for a card and for OXXO voucher generation, confirms the `back_urls` redirects and that the voucher shown to the customer is Mercado Pago's. |

**Added in conversion:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P16-V04 | unit (`integrations`) | `api/tests/unit/payments/test_mercadopago_adapter.py::test_p16_v04_preference_payload` | With a fake SDK client, `create_checkout` sends `items` with `unit_price` in pesos via `cents_to_pesos`, `external_reference = public_id`, the `notification_url`, the three `back_urls`, installments from `PAYMENT_INSTALLMENT_OPTIONS`, and `expiration_date_to = payment_deadline_at`; it returns the preference's checkout URL. |
| P16-V05 | unit (`integrations`) | `api/tests/unit/payments/test_mercadopago_adapter.py::test_p16_v05_status_mapping[fixture]` | Each captured sandbox payment response maps to the `NormalizedStatus` in the 16.3 table, amounts convert through `pesos_to_cents`, and a pending OXXO payment yields its voucher URL and expiry. A response with a refunded amount below the transaction amount maps to `partially_refunded`. |
| P16-V06 | unit (`integrations`) | `api/tests/unit/payments/test_mercadopago_adapter.py::test_p16_v06_verify_captured_notifications` | Captured sandbox notifications verify with `MP_WEBHOOK_SECRET` and return a `WebhookRef` whose `notification_id` is the stable delivery id chosen in 16.4; an altered body, a wrong secret and a stale timestamp return `None`. |
| P16-V07 | unit (`integrations`) | `api/tests/unit/payments/test_mercadopago_adapter.py::test_p16_v07_refunds` | With a fake SDK client, a card refund calls the refunds API with the amount in pesos and returns a `RefundResult`; a cash (OXXO) payment raises `RefundNotSupported` without calling the API. |

**Fixtures and factories introduced:**

- Captured Mercado Pago payment responses and notifications under `api/tests/fixtures/mercadopago/`, with secrets removed
- `fake_mp_sdk` — a fake SDK client recording calls, for the adapter unit tests
- `MercadoPagoSandboxDriver` — the 9.13 driver for the sandbox

### Phase 17 — Email provider and DNS

**Deliverable:** transactional email delivered through the real provider selected with `EMAIL_PROVIDER` (§4.3), from an authenticated sending domain (SPF, DKIM, DMARC). Requires S3 and S4.

**Release 1 scope:** all tasks.

#### Tasks

- [ ] **T17.1 — Email provider adapter**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P17-V01, P17-V02
  - Depends on: Phase 16 closed, S4
  - Context: §4.3 (Interfaces, Boundaries); §4.7; 11.1, 11.4
  - Open items: S4 (blocking)

Provider: Resend (simplest) or AWS SES (cheapest), implemented as `resend.py` or `ses.py` in `apps/notifications/email/` and selected with `EMAIL_PROVIDER` (§4.3). The adapter sends the HTML, the text part, `reply_to` and every attachment of `OutgoingEmail` (the CFDI PDF and XML, REQ-060), returns the provider message id, and maps every provider failure to `EmailSendError`, so the outbox retries (11.1). Its tests carry the `integrations` marker (§0.3); they use a fake client and no network.

- [ ] **T17.2 — Sending domain and DNS records**
  - Release: R1 · Gate: phase-close
  - REQs: —
  - Verifies: P17-V03 [manual], P17-V04 [manual], P17-V05 [manual]
  - Depends on: T17.1, S3
  - Context: §4.7 (`DEFAULT_FROM_EMAIL`, `EMAIL_REPLY_TO`); 11.4
  - Open items: S3 (blocking)
  - Done when: the three manual checks are recorded in the phase-close report.

Configure SPF, DKIM and DMARC on the sending domain (S4). Without them, Gmail will silently bin order confirmations and the owner will think orders are being lost. Set `DEFAULT_FROM_EMAIL` to the `noreply@` sender and `EMAIL_REPLY_TO` to the monitored inbox on the domain (11.4). The agent lists the DNS records; the owner adds them (§0.1 step 12).

#### Verify — test specification

> Every ID below is a named test (§4.6). The phase closes when every in-scope ID passes in `make test-all` (§0.2). ⚠️ G# marks a test written against a gap's proposed resolution, `xfail(strict=True, reason="G#")` until the gap is decided (§2.4). `[R2]` marks an ID outside Release 1; `[manual]` an ID checked by hand in the phase-close report.

IDs whose layer says `integrations` pass in `make test-integrations` (§0.3). Refusing `EMAIL_PROVIDER=file` in production is P1-V14.

**From the plan's checklist:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P17-V03 [manual] | manual | Phase-close report | Every R1 template renders correctly in Gmail, Outlook and on a phone (moved from Phase 11). |
| P17-V04 [manual] | manual | Phase-close report | A native Spanish speaker reviews every R1 template's copy, using the P11-V01 `syrupy` snapshots (moved from P11-V04), against DS voice and microcopy (CR-32). |
| P17-V05 [manual] | manual | Phase-close report | `mail-tester.com` or equivalent scores the sending domain 8/10 or better, with SPF, DKIM and DMARC passing. |

**Added in conversion:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P17-V01 | unit (`integrations`) | `api/tests/unit/notifications/test_provider_sender.py::test_p17_v01_sender_builds_request` | With a fake client, the selected adapter (`resend.py` or `ses.py`) sends `to`, `subject`, the HTML and text parts, `reply_to`, and every attachment with its filename, content type and bytes, and returns the provider message id. |
| P17-V02 | unit (`integrations`) | `api/tests/unit/notifications/test_provider_sender.py::test_p17_v02_errors_map_to_email_send_error` | Every provider failure (rejected recipient, throttling, network error) raises `EmailSendError`, so `send_outbox` keeps the row pending and increments `attempts`. |

**Fixtures and factories introduced:**

- `fake_email_client` — a fake provider client recording requests, for the adapter unit tests

### Phase 18 — Object storage and CDN

**Deliverable:** product images stored in Lightsail Object Storage with `MEDIA_STORAGE=s3` (§4.3) and served through the CDN, by both Django and `@nuxt/image`. Requires S1.

**Release 1 scope:** all tasks.

#### Tasks

- [ ] **T18.1 — S3 media storage**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P18-V01
  - Depends on: Phase 17 closed, S1
  - Context: §4.3 (Boundaries: Media storage); §4.7
  - Open items: S1 (blocking)

With `MEDIA_STORAGE=s3` (§4.3), point `django-storages` (S3 backend) at Lightsail Object Storage (S3-compatible), so the image derivatives from 3.5 are stored there. Serve them through the CDN distribution (moved from 3.5). The backend is named as a dotted string in `STORAGES`; app code keeps calling `providers.media_store()`.

- [ ] **T18.2 — Bucket and CDN**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P18-V04 [manual], P18-V05 [manual]
  - Depends on: T18.1
  - Context: §4.4 (CFDI documents); 21.5

Object storage bucket for product images, public-read on the image prefix only, with the CDN in front. Lifecycle rule to expire orphaned uploads after 30 days. The `backups/` prefix (21.5) is private. CFDI documents never go to object storage (§4.4). The agent lists the console steps; the owner performs them (§0.1 step 12).

- [ ] **T18.3 — Image provider for the storefront**
  - Release: R1 · Gate: phase-close
  - REQs: —
  - Verifies: P18-V02, P18-V03 [manual]
  - Depends on: T18.2
  - Context: §4.3; 12.8

Configure `@nuxt/image` with the CDN as provider when `CDN_BASE_URL` is set, and the `none` provider otherwise (moved from 12.8).

#### Verify — test specification

> Every ID below is a named test (§4.6). The phase closes when every in-scope ID passes in `make test-all` (§0.2). ⚠️ G# marks a test written against a gap's proposed resolution, `xfail(strict=True, reason="G#")` until the gap is decided (§2.4). `[R2]` marks an ID outside Release 1; `[manual]` an ID checked by hand in the phase-close report.

**From the plan's checklist:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P18-V03 [manual] | manual | Phase-close report | An uploaded 3000px JPEG produces three WebP derivatives in object storage (moved from Phase 3). |
| P18-V04 [manual] | manual | Phase-close report | Product images serve from the CDN with a cache hit on the second request. |

**Added in conversion:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P18-V01 | unit | `api/tests/unit/core/test_storage_settings.py::test_p18_v01_s3_storage_config` | With `MEDIA_STORAGE=s3` and the §4.7 variables set, `STORAGES["default"]["BACKEND"]` is the `django-storages` S3 backend as a dotted string, with the bucket and endpoint from the environment; with `MEDIA_STORAGE=local` it is `FileSystemStorage`. No import of `storages` or `boto3` happens. |
| P18-V02 | unit | `web/tests/unit/config/image-provider.test.ts` › `p18_v02 cdn provider only when configured` | The resolved `@nuxt/image` options use the `none` provider without `CDN_BASE_URL`, and the CDN provider with that base URL when it is set. |
| P18-V05 [manual] | manual | Phase-close report | Anonymous reads succeed on the image prefix only; `backups/` and every other prefix return access denied. |

**Fixtures and factories introduced:**

- None.

### Phase 19 — Carrier integration

**Deliverable:** `ManualCarrier` in `apps/shipping/carriers/manual.py` implements `CarrierProvider` (§4.3) and is selected with `CARRIER_PROVIDER=manual`. Staff buy labels on the carrier's or aggregator's website and type the tracking number into the admin; the site builds the customer-facing tracking link. There is still no carrier API (A7). Requires S7.

**Acceptance criterion:** the carrier contract suite from 10.13 — the same scenarios Part A runs against the mock — passes with `CARRIER_PROVIDER=manual` (P19-V01).

**Release 1 scope:** all tasks.

#### Tasks

- [ ] **T19.1 — Carrier account**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: [no-test: account setup and runbook notes; P19-V04 checks a real label]
  - Depends on: Phase 18 closed, S7
  - Context: §4.7 (`MANUAL_CARRIER_*`)
  - Open items: S7 (blocking)
  - Done when: `RUNBOOK.md` records how a label is bought, how a collection is scheduled, and where to find the cost for `shipment.cost_cents`.

Carrier account (S7). Open the account with the chosen carrier or aggregator, then record the steps above in `RUNBOOK.md`.

- [ ] **T19.2 — Manual carrier**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P19-V02
  - Depends on: T19.1
  - Context: §4.3 (Interfaces, Boundaries); 10.9

`ManualCarrier`, `code = "manual"`. One carrier at launch (A7), configured with `MANUAL_CARRIER_NAME` and `MANUAL_CARRIER_TRACKING_URL_TEMPLATE` (a URL containing `{tracking}`).

- `create_shipment` requires a tracking number and raises `TrackingNumberRequired` without one. It builds `tracking_url` from the template.
- `get_status` always returns `UNKNOWN`, so delivery is marked by staff through T11 in the 8.5 action bar.

- [ ] **T19.3 — Required tracking number in the admin**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P19-V03
  - Depends on: T19.2
  - Context: 10.1

Admin. When the active carrier raises `TrackingNumberRequired`, the shipment form shows the tracking number as a required field and reports a missing value as a field error, not a 500.

- [ ] **T19.4 — Manual carrier contract driver**
  - Release: R1 · Gate: phase-close
  - REQs: REQ-041
  - Verifies: P19-V01, P19-V04 [manual]
  - Depends on: T19.3
  - Context: 10.13; §4.6

`ManualDriver` for the 10.13 suite:

- CAR-02 takes the `TrackingNumberRequired` branch.
- CAR-04 and CAR-05 cannot be driven, because the manual carrier never reports status. `supports()` returns that reason.
- CAR-07 still runs.

The manual carrier needs no SDK and no network, so the suite runs offline in `make test-all`, next to the mock run (P10-V01).

#### Verify — test specification

> Every ID below is a named test (§4.6). The phase closes when every in-scope ID passes in `make test-all` (§0.2). ⚠️ G# marks a test written against a gap's proposed resolution, `xfail(strict=True, reason="G#")` until the gap is decided (§2.4). `[R2]` marks an ID outside Release 1; `[manual]` an ID checked by hand in the phase-close report.

The Part A suite keeps passing with `CARRIER_PROVIDER=mock` in `make test-all` (P10-V01).

**From the plan's checklist:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P19-V01 | contract | `api/tests/contract/carrier/test_manual_suite.py::test_p19_v01_manual_suite` | With `CARRIER_PROVIDER=manual`, every scenario CAR-01 to CAR-07 passes through `ManualDriver`, except CAR-04 and CAR-05, which are skipped with the reason returned by `supports()`. No other skip. |
| P19-V03 | integration | `api/tests/integration/shipping/test_manual_admin.py::test_p19_v03_missing_tracking_number_field_error` | Under the manual carrier, saving a shipment without a tracking number re-renders the form with a field error on the tracking number; no shipment is created and no transition fires. |
| P19-V04 [manual] | manual | Phase-close report | For a real label, the generated tracking URL opens the real carrier's tracking page. |

**Added in conversion:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P19-V02 | unit | `api/tests/unit/shipping/test_manual_carrier.py::test_p19_v02_tracking_url_template` | `create_shipment` with a tracking number returns a `ShipmentRef` whose `tracking_url` is the template with `{tracking}` replaced; without one it raises `TrackingNumberRequired`; `get_status` returns `UNKNOWN`. A template without `{tracking}` raises `ImproperlyConfigured` at startup. |

**Fixtures and factories introduced:**

- `ManualDriver` — the 10.13 driver for the manual carrier

### Phase 20 — Deployment, CI/CD and cost

**Deliverable:** `git push` to `main` ships to production, with migrations applied and zero manual steps.

**Release 1 scope:** all tasks, plus the production scheduler (G23).

#### 20.A Topology

One **Lightsail container service** running the containers below in a single deployment:

| Container | Image | Role |
|---|---|---|
| `proxy` | `caddy:2-alpine` | Public endpoint. Routes `/api`, `/admin`, `/static` → `api`; everything else → `web` |
| `api` | Django + gunicorn | 2 workers, 2 threads |
| `web` | Nuxt `.output` on Node 22 | SSR |
| `scheduler` | The `api` image | Runs `supercronic infra/crontab` (§4.8). Proposed by G23; a process supervisor inside `api` is the alternative. |

Plus a **Lightsail managed PostgreSQL** instance, a **Lightsail object storage bucket** for images, and a **Lightsail CDN distribution** in front of the container service.

#### 20.C Cost

The monthly cost estimate and the payment-fee comparison are in Appendix C (C.3). Set the AWS billing alarm at $80 (S1): a misconfigured CDN or a runaway image-processing loop should page the owner, not surprise them at month end.

#### Tasks

- [ ] **T20.1 — API image**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: [no-test: P20-V02 (T20.2) checks both Dockerfiles]
  - Depends on: Phase 19 closed
  - Context: §4.3 (CR-23); 20.A

`api/Dockerfile` — multi-stage, `python:3.12-slim`, non-root user, `uv sync --frozen --group integrations` (vendor SDKs, CR-23), `collectstatic` at build time, WhiteNoise serving `/static`. Entrypoint:

```sh
#!/bin/sh
set -e
python manage.py migrate --no-input
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --threads 2 \
     --access-logfile - --error-logfile -
```

Running `migrate` in the entrypoint is safe with a single node and removes a whole class of "forgot to migrate" incidents. **If you ever scale to more than one node, move this to a separate step** — concurrent migrations will corrupt state (R-07). The `scheduler` container uses the same image with its own command, so it must not run `migrate`.

- [ ] **T20.2 — Web image**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P20-V02
  - Depends on: T20.1
  - Context: §4.5 (Install and access)

`web/Dockerfile` — multi-stage: build with `pnpm install --frozen-lockfile && pnpm build`, receiving `NODE_AUTH_TOKEN` as a build secret for the DS packages, never as a build argument or environment variable (§4.5); run `node .output/server/index.mjs` on `node:22-slim`.

- [ ] **T20.3 — Lightsail deployment spec**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P20-V01
  - Depends on: T20.2
  - Context: 20.A; T1.16

`infra/lightsail/containers.json` and `public-endpoint.json`. Public endpoint → `proxy`, port 80, health check path `/api/health/`, 3 healthy / 2 unhealthy thresholds. Every secret appears as a `${VAR}` placeholder filled by `envsubst` at deploy time (T20.6).

- ~~**T20.4 — Health endpoint**~~ Absorbed by T1.16 (the endpoint) and T20.3 (the health-check configuration), per G1's resolution (ADR-0028).

- [ ] **T20.10 — Production scheduler**
  - Release: R1 · Gate: task
  - REQs: REQ-022
  - Verifies: P20-V09
  - Depends on: T20.3
  - Context: 20.A; §4.8
  - Open items: G23 (tests xfail until decided)

Per G23's proposed resolution, add the `scheduler` container to `containers.json`: the `api` image running `supercronic infra/crontab`, with the same environment as `api`. `infra/crontab` is the single source for the jobs in §4.8; `pg_backup` (21.5) is added in Phase 21.

- [ ] **T20.5 — Secrets**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: [no-test: P20-V01 (T20.3) asserts that the deployment spec holds no secret literal]
  - Depends on: T20.10
  - Context: §4.7; CR-50

Secrets as container environment variables set in the Lightsail deployment (from GitHub Actions secrets). Never in the image, never in Git. Rotate `SECRET_KEY` and the Mercado Pago token independently. The agent lists the secrets to create; the owner creates them (§0.1 step 12).

- [ ] **T20.7 — Production database**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P20-V07 [manual]
  - Depends on: T20.5
  - Context: 20.A; 21.5
  - Done when: the retention window of the automated backups is recorded in `RUNBOOK.md`.

Database: Lightsail managed PostgreSQL, Micro bundle, **not** publicly accessible. Automated daily backups on. Record the retention window.

- [ ] **T20.8 — DNS and TLS**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: [no-test: P20-V03 (T20.6) checks HTTPS, the redirect and HSTS after each deploy]
  - Depends on: T20.7, S3
  - Context: §4.7 (`ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `SITE_URL`)
  - Open items: S3 (blocking)

DNS: Route 53 hosted zone; apex and `www` → the CDN distribution. TLS certificate issued through Lightsail. Force HTTPS; HSTS on.

- ~~**T20.9 — Staging**~~ Recorded as a decision in ADR-0015 (no staging at launch): the Part A stack with every provider mocked, plus the Phase 16 sandbox run, stands in, and `main` deploys straight to production behind health checks. Revisit when revenue justifies a second environment.

- [ ] **T20.6 — Deploy workflow and rollback**
  - Release: R1 · Gate: phase-close
  - REQs: —
  - Verifies: P20-V03, P20-V04 [manual], P20-V05 [manual], P20-V06 [manual], P20-V08 [manual]
  - Depends on: T20.8
  - Context: 20.A; §0.3; T1.9
  - Open items: D1 (blocking: the legal entity owns the AWS and payment accounts)
  - Done when: `infra/rollback.sh` has been run successfully at least once, and the run is recorded in `RUNBOOK.md`.

`.github/workflows/deploy.yml`, on push to `main` after CI passes:

```yaml
- aws-actions/configure-aws-credentials   # IAM user, lightsail:* scoped to this service
- aws lightsail push-container-image --service-name cupnoobles --label api --image ...
- aws lightsail push-container-image --service-name cupnoobles --label web --image ...
- envsubst < infra/lightsail/containers.json > /tmp/containers.json
- aws lightsail create-container-service-deployment \
    --service-name cupnoobles \
    --containers file:///tmp/containers.json \
    --public-endpoint file://infra/lightsail/public-endpoint.json
- poll `aws lightsail get-container-services` until state is RUNNING (timeout 10 min)
- smoke: https://<domain>/api/health/ returns 200; http:// redirects to https://; the response carries HSTS
```

Lightsail deployments are blue/green by default: the new version must pass health checks before traffic moves. Rollback is `create-container-service-deployment` with the previous image labels — script it as `infra/rollback.sh` and test it **before** you need it.

#### Verify — test specification

> Every ID below is a named test (§4.6). The phase closes when every in-scope ID passes in `make test-all` (§0.2). ⚠️ G# marks a test written against a gap's proposed resolution, `xfail(strict=True, reason="G#")` until the gap is decided (§2.4). `[R2]` marks an ID outside Release 1; `[manual]` an ID checked by hand in the phase-close report.

The plan's first two checklist items — `make test-all` green in CI on `main`, and branch protection blocking a red pull request — are now P1-V23 in Phase 1 (G29, ADR-0029).

**From the plan's checklist:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P20-V03 | CI | `.github/workflows/deploy.yml` job `smoke` › `p20_v03 https and hsts smoke` | After each deployment, `https://<domain>/api/health/` returns 200, `http://<domain>/` redirects to `https://`, and the response carries `Strict-Transport-Security`. A failure fails the deploy job. |
| P20-V04 [manual] | manual | Phase-close report | A push to `main` is live within 10 minutes, with no manual step. |
| P20-V05 [manual] | manual | Phase-close report | A deliberately broken health check blocks the deployment and leaves the old version serving. |
| P20-V06 [manual] | manual | Phase-close report | `infra/rollback.sh` restores the previous version, tested at least once. |
| P20-V07 [manual] | manual | Phase-close report | The database is not reachable from the public internet. |
| P20-V08 [manual] | manual | Phase-close report | The billing alarm fires on a test threshold. |

**Added in conversion:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P20-V01 | unit | `api/tests/architecture/test_deploy_spec.py::test_p20_v01_container_spec` | After `envsubst` with dummy values, `containers.json` declares `proxy`, `api` and `web`; the public endpoint targets `proxy` on port 80 with health check path `/api/health/` and 3 healthy / 2 unhealthy thresholds; every secret value is a `${VAR}` placeholder before substitution. |
| P20-V02 | unit | `api/tests/architecture/test_deploy_spec.py::test_p20_v02_dockerfiles` | `api/Dockerfile` runs as a non-root user, installs the `integrations` group and runs `collectstatic` at build time; `web/Dockerfile` reads `NODE_AUTH_TOKEN` only as a build secret, never through `ARG` or `ENV`. |
| P20-V09 | unit | `api/tests/architecture/test_deploy_spec.py::test_p20_v09_scheduler_and_crontab` | `containers.json` declares a `scheduler` container from the `api` image running `supercronic infra/crontab`; `infra/crontab` holds every R1 command of the §4.8 table at its stated frequency (`pg_backup` from T21.5 on), and no command absent from the table. ⚠️ G23 |

**Fixtures and factories introduced:**

- `rendered_container_spec` — `containers.json` after `envsubst` with dummy values

### Phase 21 — Observability, backups and the runbook

**Deliverable:** the owner finds out about problems before customers report them, and can restore the database from scratch.

**Release 1 scope:** all tasks.

#### Tasks

- [ ] **T21.1 — Error tracking**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P21-V01 [manual]
  - Depends on: Phase 20 closed, S6
  - Context: §4.3 (Boundaries: Error tracking); §4.7
  - Open items: S6 (blocking)

Sentry in both `api` and `web` via `ERROR_TRACKING=sentry` and `NUXT_PUBLIC_ERROR_TRACKING=sentry` (§4.3), with `release` set to the Git SHA and the environment tagged. Alert to email or Telegram on new issues.

- [ ] **T21.2 — Structured logging**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P21-V07
  - Depends on: T21.1
  - Context: 8.1, 9.3

Structured JSON logging to stdout. Lightsail captures container logs; `aws lightsail get-container-log` retrieves them. Log every order state transition and every webhook at INFO with the order number.

- [ ] **T21.3 — Uptime monitoring**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P21-V02 [manual]
  - Depends on: T21.2
  - Context: T1.16

Uptime monitoring (UptimeRobot free): `/api/health/` and the homepage, 5-minute interval, alert after two failures. The owner creates the monitors; the agent lists them (§0.1 step 12).

- [ ] **T21.4 — Daily digest**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P21-V03 [manual], P21-V06
  - Depends on: T21.3
  - Context: §4.8; T4.9; T10.14; T9.14

Business alerts that actually matter — a daily `manage.py daily_digest` email to the owner:

- orders placed, paid and shipped in the last 24 h
- orders stuck in `pending_payment` past their deadline
- `webhook_event` rows unprocessed or failing
- `email_outbox` rows with `attempts >= 3`
- `check_stock_integrity` failures (the command is built in T4.9)
- low-stock variants
- CFDI requests waiting to be issued, and refunded orders whose CFDI needs the accountant's review (REQ-060)

One email a day that the owner actually reads beats a dashboard nobody opens.

- [ ] **T21.5 — Backups**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P21-V08
  - Depends on: T21.4
  - Context: §4.3 (Media storage); §4.8; T18.2

Backups, two layers:

1. Lightsail automated daily database snapshots (built in, T20.7).
2. `manage.py pg_backup` — a weekly `pg_dump`, gzipped, saved through `providers.media_store()` under `backups/` (private, T18.2), with a lifecycle rule keeping 8 weeks. Add its weekly line to `infra/crontab` (§4.8). Independent of AWS's own snapshots, so a catastrophic account-level mistake is survivable. The `api` image includes the PostgreSQL client tools.

- [ ] **T21.6 — Practise a restore**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P21-V04 [manual]
  - Depends on: T21.5
  - Context: T20.7
  - Done when: the restore date is recorded in `RUNBOOK.md`.

**Practise a restore.** Create a fresh Lightsail database from a snapshot, point a local API container at it, and confirm the data is intact. Do this once now and once a quarter. An untested backup is not a backup.

- ~~**T21.7 — Stock integrity check**~~ Absorbed by T4.9, per G24 (ADR-0034): the command and its daily line in `infra/crontab` are built there, and T21.4 reports its result.

- [ ] **T21.8 — Runbook**
  - Release: R1 · Gate: phase-close
  - REQs: —
  - Verifies: P21-V05 [manual]
  - Depends on: T21.6
  - Context: §4.8; 9.7, 9.8; T4.7; T10.14, T10.15
  - Done when: `RUNBOOK.md` covers every topic below.

`RUNBOOK.md` in the repo, covering:

- deploy and rollback
- restore the database from a snapshot
- a webhook was missed → run `reconcile_payments`
- a customer says they paid but the order is pending → look up the payment in the Mercado Pago dashboard, compare it with the `payment` row, run reconciliation
- stock is wrong → read `stock_ledger` for the variant, find the missing movement, `adjust_stock` with a note
- goods arrived → record them with "Recibir mercancía" in the admin, never by editing stock
- the CFDI routine → work the admin CFDI queue every day: issue each CFDI outside the store, then record the folio, UUID, PDF and XML; hand refunded invoiced orders to the accountant; run the global-invoice export for each period the accountant sets (D16)
- rotate credentials
- daily discipline: read the digest, record receipts, clear the CFDI queue

In Release 2, add the counter-sale routines: record counter sales before closing, and fix a forgotten one with `adjust_stock(reason='count_correction')` and a note.

#### Verify — test specification

> Every ID below is a named test (§4.6). The phase closes when every in-scope ID passes in `make test-all` (§0.2). ⚠️ G# marks a test written against a gap's proposed resolution, `xfail(strict=True, reason="G#")` until the gap is decided (§2.4). `[R2]` marks an ID outside Release 1; `[manual]` an ID checked by hand in the phase-close report.

**From the plan's checklist:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P21-V01 [manual] | manual | Phase-close report | A deliberate exception appears in Sentry within a minute, with the release SHA. |
| P21-V02 [manual] | manual | Phase-close report | Stopping the API triggers an uptime alert. |
| P21-V03 [manual] | manual | Phase-close report | The daily digest arrives from production, with numbers that match the admin. |
| P21-V04 [manual] | manual | Phase-close report | A restore from snapshot has been completed and the date recorded in `RUNBOOK.md`. |
| P21-V05 [manual] | manual | Phase-close report | `check_stock_integrity` passes on production data. |

**Added in conversion:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P21-V06 | integration | `api/tests/integration/ops/test_daily_digest.py::test_p21_v06_digest_contents` | With seeded data, the digest counts the orders placed, paid and shipped in the last 24 h, and lists the overdue `pending_payment` orders, unprocessed or failing webhook rows, outbox rows with `attempts >= 3`, integrity failures, low-stock variants, CFDI requests waiting, and refunded orders whose CFDI needs review. An empty section says so; nothing outside the 24-hour window is counted. |
| P21-V07 | unit | `api/tests/unit/core/test_logging.py::test_p21_v07_json_logs` | Every order transition and every webhook writes one log line at INFO that parses as JSON and carries the order number. |
| P21-V08 | integration | `api/tests/integration/ops/test_pg_backup.py::test_p21_v08_backup_round_trip` | With local media storage, `pg_backup` writes a gzipped dump under `backups/` named with its date, and the dump restores into an empty database with the same row counts. |

**Fixtures and factories introduced:**

- `digest_dataset` — orders, webhooks, outbox rows, CFDI requests and stock in every state the digest reports

### Phase 22 — Launch (Release 1)

**Deliverable:** the store is open: Release 1.

**Release 1 scope:** the launch checklist, as the Verify items below. Most are checked by hand; their evidence goes in the task reports and the phase-close report.

The plan's checklist had no tasks. Five tasks now own its items, grouped as in the plan. Each lists the decisions it needs; none of them is invented by the agent (§0.1 step 4).

#### Tasks

- [ ] **T22.1 — Legal pages and business details**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P22-V01 [manual], P22-V02 [manual], P22-V03 [manual]
  - Depends on: Phase 21 closed
  - Context: 12.A (`/legal/*`); §2.4 (D1, D2, D16); T21.8
  - Open items: D1, D2, D16 (blocking)

Publish the legal texts the owner supplies (D2) on the `/legal/*` routes, and the business details and RFC in the site footer (D1). Replace the sample CFDI catalog with the codes the accountant confirmed, without the `[PLACEHOLDER]` comment (D16). The agent publishes the texts it is given; it never drafts legal text (CR-45).

- [ ] **T22.2 — Payments go live**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P22-V05 [manual], P22-V06 [manual], P22-V07 [manual], P22-V08 [manual]
  - Depends on: T22.1, S2
  - Context: Phase 16; 9.8; T10.14
  - Open items: S2 (production verification), D13 (blocking)

Swap in the Mercado Pago production credentials and webhook secret (the owner sets them as secrets, T20.5), register the production webhook URL, and run one real low-value purchase end to end. The agent lists the steps; the owner performs them (§0.1 step 12).

- [ ] **T22.3 — Launch data**
  - Release: R1 · Gate: task
  - REQs: REQ-065
  - Verifies: P22-V09 [manual], P22-V10 [manual], P22-V11 [manual], P22-V12 [manual], P22-V13 [manual], P22-V14 [manual], P22-V15 [manual]
  - Depends on: T22.2
  - Context: §2.5; 3.6; 6.6; T4.7; T2.9
  - Open items: D4, D5, D12, D15 (blocking)

Load the production data, replacing every §2.5 dev default:

- Run `manage.py seed_states` (built in T2.7; idempotent) in the deploy step, so production has the 32 states (G41, ADR-0032).
- Import the catalog with `manage.py import_catalog <file>` from a file outside the repository (D12, CR-49).
- Record the counted opening stock with "Recibir mercancía" — every future number depends on it.
- Seed the shipping zones and rates (D5), the warehouse location (D4), and the purchase limits (D15).
- Load the full SEPOMEX dataset: `manage.py load_postal_codes` with `POSTAL_CODE_DATASET=sepomex` and a downloaded file path (G30).
- Run `manage.py check_placeholders` until it exits 0.

- [ ] **T22.4 — Technical readiness**
  - Release: R1 · Gate: task
  - REQs: —
  - Verifies: P22-V16 [manual], P22-V17 [manual], P22-V18, P22-V19 [manual], P22-V20 [manual]
  - Depends on: T22.3
  - Context: §0.2; 12.7; T4.9
  - Open items: D18 (blocking)
  - Done when: `/ui-review` ran on the changed storefront files (§0.5); findings fixed or registered.

Confirm every Release 1 phase-close report is complete, and `check_stock_integrity` is clean on the opening stock. Serve a `robots.txt` that allows crawling and names the sitemap (pre-launch mode keeps `noindex` on the pages, P12-V28), and submit the sitemap to Google Search Console. Install the analytics the owner chooses, if any (D18), and update the aviso de privacidad to match. The branded 404 and 500 pages are already covered by P12-V20 and P12-V25.

- [ ] **T22.5 — Soft launch**
  - Release: R1 · Gate: phase-close
  - REQs: —
  - Verifies: P22-V21 [manual], P22-V22 [manual], P22-V23 [manual]
  - Depends on: T22.4
  - Context: §3.7 (REQ-062); 15.B
  - Open items: —

Publish the catalog and turn pre-launch mode off in the admin (G32, ADR-0038). The owner places one delivery order on a real phone, as a customer would. Open to a small group first, and read the daily digest for a week before promoting publicly.

- [ ] **T22.6 — Pre-order terms**
  - Release: R2 · Gate: —
  - REQs: —
  - Verifies: P22-V04 [R2] [manual]
  - Depends on: Phase 22 closed
  - Context: 10.3 (FIFO allocation); §2.4 (D9)
  - Open items: D9 (blocking)

Publish the pre-order terms the owner supplies, including the FIFO allocation rule (10.3) and the cancellation policy (D9), before the first pre-order is offered.

#### Verify — test specification

> Every ID below is a named test (§4.6). The phase closes when every in-scope ID passes in `make test-all` (§0.2). ⚠️ G# marks a test written against a gap's proposed resolution, `xfail(strict=True, reason="G#")` until the gap is decided (§2.4). `[R2]` marks an ID outside Release 1; `[manual]` an ID checked by hand in the phase-close report.

**Legal and business:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P22-V01 [manual] | manual | Task report T22.1 | The terms of service, aviso de privacidad, shipping policy, returns policy and purchase-limits text are published (D2). |
| P22-V02 [manual] | manual | Task report T22.1 | The business details and RFC are in the site footer (D1). |
| P22-V03 [manual] | manual | Task report T22.1 | The accountant has confirmed the CFDI fields and codes (D16); `api/fixtures/cfdi_catalogs.json` holds them without the `[PLACEHOLDER]` comment; the CFDI routine is in `RUNBOOK.md`. |
| P22-V04 [R2] [manual] | manual | Task report T22.6 | The pre-order terms are published, including the FIFO allocation rule and the cancellation policy (D9). |

**Payments:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P22-V05 [manual] | manual | Task report T22.2 | Mercado Pago production credentials are in place, and the test credentials are removed from the production configuration. |
| P22-V06 [manual] | manual | Task report T22.2 | The production webhook URL is registered and its signing secret configured. |
| P22-V07 [manual] | manual | Task report T22.2 | One real low-value purchase completes end to end with a real card, with a CFDI requested and issued; it is then refunded, and the refund flags the CFDI for the accountant's review. |
| P22-V08 [manual] | manual | Task report T22.2 | The payout bank account is verified and the settlement schedule set (D13). |

**Data:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P22-V09 [manual] | manual | Task report T22.3 | The catalog is imported and spot-checked; every active product has at least one image and a price (D12). |
| P22-V10 [manual] | manual | Task report T22.3 | The physical stock is counted and recorded as receipts: the opening balance. |
| P22-V11 [manual] | manual | Task report T22.3 | Shipping zones and rates are seeded and checked against real carrier quotes (D5). |
| P22-V12 [manual] | manual | Task report T22.3 | The warehouse location is configured (D4) and is never shown as a store (CR-47). |
| P22-V13 [manual] | manual | Task report T22.3 | The purchase limits are set on the limited variants (D15). |
| P22-V14 [manual] | manual | Task report T22.3 | The full SEPOMEX dataset is loaded (G30). |
| P22-V15 [manual] | manual | Task report T22.3 | `manage.py check_placeholders` exits 0 against production: no dev default from §2.5 and no `[DEMO]` row remains (REQ-065). |

**Technical:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P22-V16 [manual] | manual | Task report T22.4 | Every Release 1 phase-close report is complete, including the Phase 16 sandbox run, the practised restore (P21-V04) and the billing alarm (P20-V08). |
| P22-V17 [manual] | manual | Task report T22.4 | `check_stock_integrity` is clean on production after the opening stock. |
| P22-V18 | E2E | `web/e2e/p22_launch.spec.ts` › `p22_v18 robots allows crawling and names the sitemap` | With pre-launch mode off, `/robots.txt` allows crawling and names `/sitemap.xml`. |
| P22-V19 [manual] | manual | Task report T22.4 | The sitemap is submitted to Google Search Console. |
| P22-V20 [manual] | manual | Task report T22.4 | The analytics chosen in D18 is installed, or none is by decision, and the aviso de privacidad matches. |

**Soft launch:**

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P22-V21 [manual] | manual | Task report T22.5 | The catalog is published and pre-launch mode is off; an anonymous visitor sees the catalog. |
| P22-V22 [manual] | manual | Task report T22.5 | The owner places one delivery order on a real phone, as a customer would (moved from P13-V01). Pickup and pre-order orders join in R2. |
| P22-V23 [manual] | manual | Phase-close report | The store opens to a small group first, and the owner reads the daily digest for a week before promoting it publicly. |

**Fixtures and factories introduced:**

- None.

## 7. Risks and decisions due by phase

### 7.1 Risks

Each mitigation names the requirement, test or open item that carries it, so the mitigation is checked rather than hoped for.

| ID | Risk | Early signal | Mitigation |
|---|---|---|---|
| R-01 | Two customers buy the last unit (plan Phase 4) | An integrity failure; a customer whose paid order can't ship | REQ-010; P4-V01, P8-V04, P8-V11; `check_stock_integrity` daily |
| R-02 | A payment notification is lost or delivered twice | An order stuck in `pending_payment` after the customer paid | REQ-030, REQ-031; PAY-09, PAY-14; `reconcile_payments` every 10 minutes |
| R-03 | An approved payment for the wrong amount moves an order | An amount-guard alert | REQ-030; P9-V07 |
| R-04 | The catalog list issues one query per product (plan 5.4) | Slow catalog pages | P5-V03 |
| R-05 | A mock is easier than its provider and hides bugs until Part B | A sandbox scenario that fails or can't be driven | REQ-041; the Phase 16 and 19 contract runs; every skip carries a reason |
| R-06 | Mercado Pago verification (S2) or email production access (S4) stalls Part B | Signup still pending at local acceptance | Start both during Part A (§5) |
| R-07 | `migrate` in the API entrypoint corrupts state on more than one node (plan 20.1) | Scaling beyond one node | Single node only; move migrations to a separate step before scaling |
| R-08 | Scheduled jobs never run in production | No `expire_reservations` activity after deploy | G23, decided before Phase 20 |
| R-09 | Order emails land in spam | Customers report missing confirmations | SPF, DKIM and DMARC (Phase 17); a mail-tester score check |
| R-10 | Payment fees, not hosting, dominate cost (plan 20.C) | Fees far above the hosting bill | D7 and D13 decided with Appendix C at hand |
| R-11 | A placeholder, demo row or dev default reaches production | `check_placeholders` non-zero | REQ-065; P2-V18, P15-V12; the Phase 22 checklist |
| R-12 | CI or an image build can't read the private DS packages | Install fails with 401 or 404 | S8; §4.5; P15-V14 builds every image from a clean clone |
| R-13 | A missing DS part blocks a storefront phase | A DSR item unreleased when its phase starts | Request early (§2.4); DS minor releases run in parallel (§5) |
| R-14 | Release 1 is not live when the owner's guide needs it | Phases closing slower than planned | The R1 cut (§1.2); decisions due early (§7.2); the guide's own fallback applies (GE:B7) |
| R-15 | Internal business data is committed to the public repository | A cost, supplier or budget figure in a diff | CR-48, CR-49; the PR checklist; GitHub secret scanning |
| R-16 | The phase-close suite gets slow enough to discourage running it | `make test-all` time rising phase over phase | OA-03 split; CI cancels superseded runs; record `make test-all` time in each phase-close report |
| R-17 | A CFDI request is missed or copied wrong, because issuing is manual | A request waiting more than a few days; a customer correction | REQ-060; the admin queue (P10-V23); the daily digest lists waiting requests |
| R-18 | A customer bypasses a purchase limit by varying email, phone and address | Several orders of a limited item to near-identical data | G31 matches any of the three; residual risk accepted (GE:R10) |
| R-19 | The hidden catalog leaks through the CDN cache before launch | A catalog page visible to an anonymous request | ~~G32~~ (ADR-0038); P5-V15 forbids public caching in pre-launch mode |
| R-20 | A failing webhook row is retried forever | `attempts` growing on one row | ~~G7~~ (ADR-0044) |
| R-21 | Server and browser render a date in different time zones (hydration mismatch) | A hydration warning; a date off by one | CR-31; G5; the `ui-review` step (§0.5) |

### 7.2 Decisions due by phase

A view of §2.4, ordered by when each item is needed. An item listed under a phase must be answered before that phase closes, or before it starts where the phase depends on it. Design gaps can be answered in batches: the engineering ones (G1–G3, G6–G8, G14–G18, G20–G26, G29, G34, G35, G37–G39, G45, G46) don't need business input; the others are visible to customers or staff.

| Needed by | Items |
|---|---|
| Before Phase 1 | S5 (repository name), ~~S8~~ |
| Phase 1 | ~~G1~~, ~~G29~~ |
| Before Phase 2 (schema) | D14 (types), D16 (fields); ~~G3~~, ~~G5~~, ~~G28~~, ~~G31~~, ~~G33~~, ~~G34~~ (§4.4) |
| Phase 3 | ~~G12~~, G39 |
| Phase 4 | ~~G2~~, ~~G15~~, ~~G20~~, ~~G24~~, ~~G34~~, ~~G37~~, ~~G38~~ |
| Phase 5 | ~~G13~~ with ~~D10~~, ~~G32~~ |
| Phase 6 | ~~G30~~, ~~G35~~ |
| Phase 8 | ~~G3~~, ~~G4~~, ~~G5~~, ~~G25~~, ~~G26~~, ~~G27~~, ~~G31~~, ~~G33~~ |
| Phase 9 | ~~G7~~, ~~G8~~, ~~G11~~, ~~G14~~, ~~G46~~ |
| Phase 11 | G17; DSR-04, DSR-05 released |
| Phase 12 | G18, ~~G28~~, ~~G32~~, D17; DSR-01, DSR-02, DSR-03, DSR-06, DSR-07 released; DSR-09 or its fallback |
| Phase 13 | G21, G22 |
| Phase 16 | S2, D6, D7, D13, G45 |
| Phase 17 | S3, S4 |
| Phase 18 | S1 |
| Phase 19 | S7 |
| Phase 20 | D1, G23 |
| Phase 21 | S6 |
| Phase 22 | D2, D4, D5, ~~D10~~, D12, D15, D16 (the rest), D18 |
| Release 2 | D8, D9, G6, G9, G10, G16, G36, DSR-08 |

## 8. Spec change log

| Spec version | Date | Change | Reference |
|---|---|---|---|
| 0.1 | 2026-10-19 | Stage 1 draft: header, §0–§2, converted from the plan, with the launch cut, manual CFDI, the skills policy and the register | OA-01 to OA-13 |
| 0.2 | 2026-10-19 | Stage 2 draft: §3 requirements with new Verify items (§3.9); §4 technical design, with the canonical schema moved to `spec/schema.sql` and the CFDI tables added; §5 phases; §7 risks and decisions due; Appendix C. §1.2 moves `/rastrear` into R1; §2 adds DSR-09 and the CFDI catalog placeholder. | OA-02, OA-07, OA-09, OA-11, OA-12 |
| 0.3 | 2026-10-19 | Stage 3 draft: §6 with all 22 phases (210 tasks, 361 Verify IDs, Part B checklists converted to IDs); Appendix A generated; Appendix E legacy map. §3.9 moved into the phase tables; REQ-041, REQ-051, REQ-064, REQ-065 and REQ-073 cite the final IDs. §2.4 adds G37–G39 and D18; §0.3 and §4.6 add `make test-integrations`. | OA-02, OA-03, OA-11 |
| 0.4 | 2026-10-19 | Stage 4: Appendix B (ADR index) and Appendix D (effort, no dates); the bootstrap pack (agent files, skills, pinned guidelines, PR template, lint config) named in Phase 1; T1.8 adds markdownlint; T1.9 keeps the bootstrap PR template. | OA-12, OA-13 |
| 1.0 | 2026-10-19 | Approved by the owner. Status set to approved for Part A; Part B stays draft until P15-V14 passes. No requirement or task changes. | OA-14 |
| 1.1 | 2026-10-20 | S8 resolved (read access granted); T1.5 no longer blocked. T1.3 names the mock values `prod.py` rejects. No requirement, Verify ID or schema change. | OA-15, OA-16, OA-17; ADR-0026, ADR-0027 |
| 1.2 | 2026-10-20 | Lighter decision process: `/decide` only for owner-only decisions; "Judgment calls" item added to the task report (§0.2); DSR-10 registered (`CnMediaCard` type error). No requirement, Verify ID or schema change. | OA-18 |
| 1.3 | 2026-10-20 | Design System pin raised to 1.0.1 (fixes DSR-10). New task T1.17; T1.8 depends on it. A17, §4.5 and the header cite 1.0.1. No requirement, Verify ID or schema change. | OA-19 |
| 1.4 | 2026-10-21 | G1 resolved: the health endpoint moves into Phase 1 (T1.16); T20.4 stays absorbed by T1.16 and T20.3; T1.16 loses its `xfail` open item. No Verify ID or schema change. | OA-20; ADR-0028 |
| 1.5 | 2026-10-23 | G29 resolved: CI and branch protection are verified in Phase 1 (P1-V23, `[manual]`), and the GitHub settings in force are recorded. T1.9 loses its open item. No Verify ID or schema change. | OA-21; ADR-0029 |
| 1.6 | 2026-10-23 | G3, G5, G28, G31, G33 and G34 resolved: the Release 1 schema additions are in `spec/schema.sql` (`product.is_featured`, `featured_position`; `variant.purchase_limit`; `stock_item.bin_location`; `order.cart_token`, `idempotency_key`, `idempotency_fingerprint`; `order_line.unit_cost_cents`). T2.1a to T2.1c, T4.8, T5.1, T8.3 to T8.9 and T10.15 to T10.17 lose their open items, and the ⚠️ markers of the matching Verify rows are removed. D15 now also covers the purchase-limit window; new setting `PURCHASE_LIMIT_WINDOW_DAYS`. No Verify ID added or removed. | OA-22 to OA-27; ADR-0030 |
| 1.7 | 2026-10-23 | G40 registered and resolved: the schema's `ON DELETE` rules are enforced by Django's ORM, not by the database, except on the four named foreign keys; revisit on Django 6.0. No requirement, Verify ID, task or schema change. | OA-28; ADR-0031 |
| 1.8 | 2026-10-23 | G41 registered and resolved: production loads `mx_state` with a separate idempotent `manage.py seed_states` command, built in T2.7 and run in T22.3. No Verify ID or schema change. | OA-29; ADR-0032 |
| 1.9 | 2026-10-24 | Phase 3 task order: T3.2 now precedes T3.1 (it was circular); "Depends on" fixed in T3.1, T3.2, T3.3 and T3.6; an execution-order note added. No Verify ID, schema or task-ID change. | OA-30 |
| 1.10 | 2026-10-24 | G12 resolved: `import_catalog` is all or nothing per file and reports every invalid row. T3.6 loses its G12 open item and P3-V09 loses its ⚠️ marker. No Verify ID, task or schema change. | OA-31; ADR-0033 |
| 1.11 | 2026-10-24 | Phase 4 task order: T4.2 now precedes T4.1 (T4.1 raised an error T4.2 defines); "Depends on" fixed in T4.1, T4.2, T4.3 and T4.8; an execution-order note added. No Verify ID, schema or task-ID change. | OA-32 |
| 1.12 | 2026-10-24 | G24 resolved: `check_stock_integrity` is built in Phase 4 (T4.9) and T21.7 stays absorbed. T4.9 loses its G24 open item and P4-V07 loses its ⚠️ marker. No Verify ID, task or schema change. | OA-33; ADR-0034 |
| 1.13 | 2026-10-25 | G20 resolved: the "Recibir mercancía" admin action calls `receive_stock` in R1 and `receive_preorder_stock` for pre-order variants in R2. T4.7, T10.3 and the Phase 15 task lose their G20 open item; P4-V19, REQ-064, P15-V05 and demo step 11 lose their ⚠️ marker. No Verify ID, task or schema change. | OA-34; ADR-0035 |
| 1.14 | 2026-10-25 | G2, G15, G37 and G38 resolved as proposed: `enqueue_email()` in Phase 4; `commit_reservations` idempotent; `expire_reservations` releases holds in Phase 4 and fires T5 through `apply_event` from Phase 8, and `advance_orders` stops firing T5 (T8.6a); `OWNER_ALERT_EMAIL` added to §4.7. T4.1, T4.3, T4.6 and T6.2 lose their open items; P4-V03 asserts the order state from Phase 8; P4-V16, P4-V17, P6-V01 and P6-V04 lose their ⚠️ marker. No Verify ID, task or schema change. | OA-35 to OA-38; ADR-0036 |
| 1.15 | 2026-10-25 | Phase 5 task order: T5.3 now precedes T5.1 and T5.2 (they depended on availability); the facets endpoint and P5-V13 move from T5.1 to T5.2; "Depends on" fixed in T5.1, T5.2, T5.3 and T5.4; an execution-order note added. No Verify ID, schema or task-ID change. | OA-39 |
| 1.16 | 2026-10-25 | D10 decided and G13 resolved: `low_stock` is `1 <= available <= 5`, with a badge and no raw counts. T5.3 loses its open items, P5-V07 loses its ⚠️ marker, and D10 leaves the blocking list of T22.3. No Verify ID, task or schema change. | OA-40; ADR-0037 |
| 1.17 | 2026-10-25 | G32 resolved: pre-launch mode is a `site_setting.prelaunch_mode` flag edited in the admin; anonymous catalog requests get `503` `{"prelaunch": true}` with `no-store`. New table `site_setting` in `spec/schema.sql`. T5.7, T12.15, T15.6b and T22.5 lose their G32 open item; P5-V15, P12-V28, P15-V16, P22-V21, REQ-062 and demo step 10 lose their ⚠️ marker. No Verify ID or task change. | OA-41; ADR-0038 |
| 1.18 | 2026-10-25 | Phase 6 task order: the tasks are listed in execution order (T6.2, T6.6, T6.7b, then the R2 tasks T6.1, T6.3, T6.4, T6.5, T6.7a, T6.8); an execution-order note added. No dependency, Verify ID, schema or task-ID change. | OA-42 |
| 1.19 | 2026-10-25 | G30 resolved: the full SEPOMEX dataset is a launch requirement and the sample stays for Part A. T6.6 no longer lists G30 as open and T22.3 no longer lists it as an open item. No Verify ID, schema or task-ID change. | OA-43, ADR-0039 |
| 1.20 | 2026-10-25 | G35 resolved: the guest order lookup is `POST /api/orders/lookup/` with a JSON body. The ⚠️ G35 mark is removed from P6-V14; T6.7b and T14.6 no longer list G35 as open. No Verify ID, schema or task-ID change. | OA-44, ADR-0040 |
| 1.21 | 2026-10-25 | Phase 7 task order: an execution-order note added (T7.9, T7.7, T7.2a, T7.1, T7.3, T7.4, T7.6, T7.5a, T7.8, then the R2 tasks T7.2b, T7.5b). No dependency, Verify ID, schema or task-ID change. | OA-45 |
| 1.22 | 2026-10-25 | G44 registered: the cart quote reads the postal code from the request, not from the cart; to be checked in Phase 13. No requirement, Verify ID, schema or task-ID change. | OA-46 |
| 1.23 | 2026-10-25 | Phase 8 task order: an execution-order note added (T8.1, T8.3, T8.10, T8.2, T8.4, T8.7, T8.8, T8.9, T8.5, T8.6a, then the R2 tasks T8.11, T8.6b). No dependency, Verify ID, schema or task-ID change. | OA-47 |
| 1.24 | 2026-10-25 | G25 resolved as proposed: `MockPaymentProvider.create_checkout` and `refund` are built in Phase 8 (T8.10), and the rest of the mock in Phase 9 (T9.9). T8.10 and T8.2 lose their G25 open item; P8-V01 and P8-V06 lose their ⚠️ marker. No Verify ID, schema or task-ID change. | OA-48; ADR-0041 |
| 1.25 | 2026-10-25 | G4 resolved as proposed: checkout takes an optional `expected_total_cents`, and a mismatch returns 409 `total_changed` with the fresh totals and reserves nothing. New task T8.12 builds it (P8-V09 moves from T8.4 to T8.12; T8.6a also depends on T8.12). The ⚠️ G4 mark is removed from P8-V09, P13-V19 and REQ-002; T8.4 and T13.6 lose their G4 open item. No other Verify ID or schema change. | OA-49; ADR-0042 |
| 1.26 | 2026-10-25 | G26 and G27 resolved as proposed: a partial refund keeps the order state (T18), and the refund events are accepted from `completed`, `expired` and `cancelled` as recorded payment events (T17, T18). 8.A rows T17 and T18 and a note after the terminal states are amended; P8-V01 and P8-V07 text follows. New task T8.13 changes `TRANSITIONS` and its tests, and T8.6a now also depends on it. G45 registered at the owner's request (refund inside the order transaction, Phase 16); T16.5 gains it as an open item. No Verify ID, schema or REQ change. | OA-50, OA-51; ADR-0043 |
| 1.27 | 2026-10-26 | Phase 9 task order: an execution-order note added (T9.1, T9.2, T9.9, T9.3, T9.4, T9.5, T9.6, T9.7, T9.8, T9.14, T9.10, T9.11, T9.12a, T9.12b, T9.13a, T9.13b), stating that forward mentions between tasks are not dependencies. No dependency, Verify ID, schema or task-ID change. | OA-52 |
| 1.28 | 2026-10-26 | G7 and G8 resolved as proposed: a failing webhook row is retried 10 times with exponential backoff, then marked failed and alerted; a notification timestamp is accepted when `abs(now − ts) ≤ WEBHOOK_MAX_AGE_SECONDS`, future side included. T9.3 and T16.4 lose their open items; the ⚠️ marks of P9-V10, P9-V13, P9-V17, P16-V06, REQ-030 and REQ-031 (G7, G8) are removed; §4.7, R-20 and §7.2 follow. No Verify ID, task or schema change. | OA-53; ADR-0044 |
| 1.29 | 2026-10-26 | `WEBHOOK_INLINE_BUDGET_MS` recorded as 2000 ms in the §4.7 row (it read "Set in 9.3"). No task, Verify ID, schema or code change. | OA-54; ADR-0045 |
| 1.30 | 2026-10-26 | G11 resolved: a `pending` voucher for an expired or cancelled order alerts and is cancelled at the provider, and the order stays as it is. No separate checkout-session TTL. New task T9.15 (`cancel_payment` on `PaymentProvider` and the mock) runs after T9.6; P9-V21 moves from T9.5 to it and loses its `xfail`; T16.3 gains the real adapter method. | OA-55; ADR-0046 |
| 1.31 | 2026-10-26 | G14 resolved as proposed: when a webhook and `reconcile_payments` process one approval at the same time, the second is a `webhook_no_op`. T9.7 loses its open item; the ⚠️ marks of P9-V14, REQ-022 and REQ-031 (G14) are removed. No Verify ID, task, schema or code change. | OA-56; ADR-0047 |
| 1.32 | 2026-10-26 | G46 resolved as proposed: a refund sets the payment's `refunded_cents` to the running total, and the T17 and T18 guards compare that total with `amount_cents`. The 8.A effects of T17 and T18 say so. T9.8 built it as written, so no code, Verify ID, task or schema change. | OA-57; ADR-0048 |
| 1.33 | 2026-10-26 | The cart is converted at T1 (the cart half of G22 and the Phase 9 question of T8.4). New task T9.16 (after T9.14) sets `cart.converted_order` in the checkout transaction and keeps the same-key replay working; new Verify ID P9-V23, added to REQ-021. G22's row narrows to the pay-retry endpoint, still open for Phase 13; T13.10 cites the decision. No schema change. | OA-58; ADR-0049 |
| 1.34 | 2026-10-26 | Phase 9 closes only when the coverage ratchet passes. New task T9.17 (after T9.13a, before T9.13b) adds tests for the branches that lowered critical coverage from 100% to 97.15% and backend from 96.58% to 95.94%; T9.13b also depends on it. The baseline is not lowered. No Verify ID, schema or code change. | Owner answer in chat, 2026-10-26 |
| 1.35 | 2026-10-26 | G48 resolved as proposed: a reservation never expires before its order's `payment_deadline_at`, both are extended together, and `expire_reservations` logs a `GuardFailed` as a one-line warning. T9.5 built it as written, so no code, Verify ID, task or schema change. | OA-59; ADR-0050 |

Amendment rule: this file changes only through an ADR, or by the owner directly. Every amendment bumps the spec version, adds a row here, and keeps every ID stable. Removed items are struck through, never renumbered.

## Appendix A — Traceability matrix

Generated from §3 and §6; from T1.14b on, `scripts/check_traceability.py` regenerates it. Each row lists a requirement, the tasks that own its acceptance IDs, and the IDs. `[R2]` IDs are outside Release 1.

| REQ | Release | Tasks | Verify IDs |
|---|---|---|---|
| REQ-001 | R1 | T2.1c, T7.9, T9.2, T12.6 | P2-V04 · P2-V10 · P7-V17 · P9-V08 · P12-V09 |
| REQ-002 | R1 | T7.3, T7.9, T8.12, T13.1, T13.6 | P7-V03 · P7-V06 · P7-V17 · P8-V09 · P13-V03 · P13-V19 |
| REQ-010 | R1 | T2.1b, T4.1, T8.6a, T8.4, T8.2, T13.6, T15.6b, T4.10 | P2-V02 · P4-V01 · P4-V09 · P4-V11 · P8-V04 · P8-V10 · P8-V11 · P13-V18 · P15-V08 · P4-V04 [R2] · P4-V14 [R2] |
| REQ-011 | R1 | T1.12b, T4.1, T4.9, T4.4 | P1-V05 · P4-V02 · P4-V06 · P4-V07 · P4-V12 · P4-V15 · P4-V18 |
| REQ-012 | R1 | T4.3, T4.1, T9.5, T15.6a | P4-V03 · P4-V05 · P4-V08 · P9-V09 · P15-V04 |
| REQ-013 | R2 | T2.1a, T10.5, T10.3 | P2-V08 · P10-V07 [R2] · P10-V14 [R2] · P10-V15 [R2] · P10-V22 [R2] |
| REQ-020 | R1 | T1.12b, T8.2, T8.1, T8.5 | P1-V05 · P8-V01 · P8-V02 · P8-V05 · P8-V07 · P8-V15 |
| REQ-021 | R1 | T8.4, T9.16, T13.3, T15.6b | P8-V03 · P8-V08 · P8-V10 · P8-V18 · P9-V23 · P13-V02 · P13-V21 · P15-V08 |
| REQ-022 | R1 | T4.1, T8.6a, T9.7, T10.11, T11.1 | P4-V05 · P8-V14 · P9-V14 · P10-V19 · P11-V10 |
| REQ-030 | R1 | T2.1c, T9.13b, T9.12b, T9.4, T9.3, T9.2 | P2-V16 · P9-V01 · P9-V05 · P9-V07 · P9-V10 · P9-V11 · P9-V12 · P9-V20 |
| REQ-031 | R1 | T9.12a, T9.3, T9.7 | P9-V04 · P9-V13 · P9-V14 · P9-V17 |
| REQ-032 | R1 | T2.1c, T8.10, T9.8 | P2-V13 · P8-V06 · P9-V15 · P9-V16 |
| REQ-040 | R1 | T1.11, T1.3, T9.12b, T9.9, T10.12, T15.3 | P1-V12 · P1-V14 · P1-V15 · P1-V16 · P1-V19 · P9-V03 · P9-V06 · P10-V04 · P15-V11 |
| REQ-041 | R1 | T9.13b, T10.13, T16.7, T19.4 | P9-V01 · P10-V01 · P16-V01 · P19-V01 |
| REQ-042 | R1 | T1.13b, T1.12a, T15.5 | P1-V08 · P1-V13 · P15-V13 · P15-V14 |
| REQ-050 | R1 | T12.14 | P12-V26 · P12-V27 |
| REQ-051 | R1 | T1.13b, T12.4, T12.9, T13.7, T14.6, T15.6a, T15.6b | P1-V09 · P1-V20 · P12-V12 · P12-V19 · P12-V21 · P13-V16 · P14-V17 · P15-V01 · P15-V03 · P15-V04 · P15-V08 |
| REQ-052 | R1 | T11.3, T12.6, T12.4, T13.7 | P11-V04 · P12-V09 · P12-V12 · P13-V14 |
| REQ-053 | R1 | T12.16, T12.10, T12.13, T13.4 | P12-V01 · P12-V03 · P12-V20 · P12-V25 · P13-V20 |
| REQ-054 | R1 | T1.12c, T5.5, T12.4, T12.11 | P1-V07 · P5-V04 · P12-V04 · P12-V24 |
| REQ-055 | R1 | T11.7, T11.6 | P11-V01 · P11-V12 · P11-V13 |
| REQ-060 | R1 | T2.1c, T8.7, T9.14, T10.14, T10.15, T11.8, T13.11, T15.6b | P2-V17 · P8-V19 · P9-V22 · P10-V23 · P10-V24 · P11-V11 · P13-V23 · P15-V15 |
| REQ-061 | R1 | T8.8, T13.12 | P8-V20 · P13-V24 |
| REQ-062 | R1 | T5.7, T12.15, T15.6b | P5-V15 · P12-V28 · P15-V16 |
| REQ-063 | R1 | T8.9, T10.16 | P8-V21 · P10-V25 |
| REQ-064 | R1 | T4.7, T4.8, T10.17 | P4-V19 · P4-V20 · P10-V26 |
| REQ-065 | R1 | T2.9, T15.8, T22.3 | P2-V18 · P15-V12 · P22-V15 |
| REQ-070 | R1 | T1.14b | P1-V10 · P1-V21 · P1-V22 |
| REQ-071 | R1 | T1.14a | P1-V06 |
| REQ-072 | R1 | T1.12a, T2.1c | P1-V04 · P2-V01 · P2-V07 |
| REQ-073 | R1 | T1.14a, T1.9, T15.5 | P1-V03 · P1-V23 · P15-V14 |

362 Verify IDs in §6; 139 are acceptance criteria of a §3 requirement. The others are feature-level checks of their phase (OA-02).

## Appendix B — ADR index

Decision records live in `docs/decisions/`, one file per decision, from the template `0000-adr-template.md`. T1.15 writes ADR-0001 to ADR-0025 with status `accepted`; §4.2 gives each decision, its choice and the alternatives. Later decisions take the next number, are written by `/decide`, and are added to this table in the same commit.

| ADR | Title | File | Source |
|---|---|---|---|
| ADR-0001 | Baseline assumptions | `docs/decisions/0001-baseline-assumptions.md` | §2.3 |
| ADR-0002 | Dev defaults are placeholders | `docs/decisions/0002-dev-defaults-are-placeholders.md` | §2.5 |
| ADR-0003 | Database: PostgreSQL with JSONB | `docs/decisions/0003-database-postgresql.md` | plan 3.1 |
| ADR-0004 | Attribute-agnostic catalog | `docs/decisions/0004-attribute-model.md` | plan 2.4 |
| ADR-0005 | Backend: Django and DRF | `docs/decisions/0005-backend-django.md` | plan 3.2 |
| ADR-0006 | Background work: cron and management commands | `docs/decisions/0006-background-work-cron.md` | plan 3.2 |
| ADR-0007 | Frontend: Nuxt 4 SSR on the Design System layer | `docs/decisions/0007-frontend-nuxt-ds-layer.md` | plan 3.3; C-01, C-02, C-11 |
| ADR-0008 | Client state: server state only | `docs/decisions/0008-server-state-only.md` | plan 3.3 |
| ADR-0009 | API client generated from OpenAPI | `docs/decisions/0009-generated-api-client.md` | plan 3.3 |
| ADR-0010 | One origin through Caddy; session auth | `docs/decisions/0010-same-origin.md` | plan §2 |
| ADR-0011 | Server-side cart; prices frozen once | `docs/decisions/0011-server-side-cart.md` | plan 7.3 |
| ADR-0012 | Payments: Mercado Pago Checkout Pro | `docs/decisions/0012-payments-mercado-pago.md` | plan 3.4 |
| ADR-0013 | Payment truth: webhook plus reconciliation | `docs/decisions/0013-payment-truth.md` | plan 9.A |
| ADR-0014 | Pre-order stock: a separate counter | `docs/decisions/0014-preorder-counter.md` | plan 10.A |
| ADR-0015 | Hosting: AWS Lightsail, no staging | `docs/decisions/0015-hosting-lightsail.md` | plan 3.5, 20.9 |
| ADR-0016 | Mock-first integration adapters | `docs/decisions/0016-integration-adapters.md` | plan §5, 9.9, 9.13 |
| ADR-0017 | Test discipline | `docs/decisions/0017-test-discipline.md` | plan §6 |
| ADR-0018 | Per-task gate and phase-close gate | `docs/decisions/0018-task-and-phase-gates.md` | OA-03 |
| ADR-0019 | CFDI issued by hand in Release 1 | `docs/decisions/0019-manual-cfdi.md` | OA-07 |
| ADR-0020 | Release 1 scope | `docs/decisions/0020-release-1-scope.md` | OA-08, OA-11 |
| ADR-0021 | Public repository | `docs/decisions/0021-public-repository.md` | OA-10 |
| ADR-0022 | Design System adoption | `docs/decisions/0022-design-system-adoption.md` | OA-09, OA-12 |
| ADR-0023 | Agent skills policy | `docs/decisions/0023-agent-skills-policy.md` | OA-13 |
| ADR-0024 | Price format | `docs/decisions/0024-price-format.md` | G19, C-08 |
| ADR-0025 | Brand assets from the Design System | `docs/decisions/0025-brand-assets.md` | D11 |
| ADR-0026 | Read access to the Design System packages | `docs/decisions/0026-ds-package-read-access.md` | S8; OA-15 |
| ADR-0027 | Which values `prod.py` rejects, and the installed apps | `docs/decisions/0027-prod-settings-mock-rejection.md` | T1.3; OA-16, OA-17 |
| ADR-0028 | Health endpoint in Phase 1 | `docs/decisions/0028-health-endpoint-phase-1.md` | G1; OA-20 |
| ADR-0029 | CI and branch protection in Phase 1 | `docs/decisions/0029-ci-branch-protection-phase-1.md` | G29; OA-21 |
| ADR-0030 | Release 1 schema additions | `docs/decisions/0030-release-1-schema-additions.md` | G3, G5, G28, G31, G33, G34; OA-22 to OA-27 |
| ADR-0031 | Foreign key delete rules are enforced by Django | `docs/decisions/0031-fk-delete-rules-in-orm.md` | G40; OA-28 |
| ADR-0032 | States are loaded in production by a separate seed command | `docs/decisions/0032-seed-states-command.md` | G41; OA-29 |
| ADR-0033 | The catalog importer is all or nothing per file | `docs/decisions/0033-import-catalog-all-or-nothing.md` | G12; OA-31 |
| ADR-0034 | The stock integrity command is built in Phase 4 | `docs/decisions/0034-stock-integrity-command-phase-4.md` | G24; OA-33 |
| ADR-0035 | Goods are received through an admin action | `docs/decisions/0035-receive-goods-admin-action.md` | G20; OA-34 |
| ADR-0036 | Phase 4 open items: outbox helper, idempotent commit, expiry job, owner alert address | `docs/decisions/0036-phase-4-open-items.md` | G2, G15, G37, G38; OA-35 to OA-38 |
| ADR-0037 | The storefront shows a low-stock badge, with no counts | `docs/decisions/0037-public-stock-display.md` | D10, G13; OA-40 |
| ADR-0038 | Pre-launch mode is a database flag edited in the admin | `docs/decisions/0038-prelaunch-mode-site-setting.md` | G32; OA-41 |
| ADR-0039 | The full SEPOMEX dataset is a launch requirement | `docs/decisions/0039-sepomex-launch-requirement.md` | G30; OA-43 |
| ADR-0040 | The guest order lookup is a POST with a JSON body | `docs/decisions/0040-guest-lookup-post.md` | G35; OA-44 |
| ADR-0041 | The mock payment provider's checkout and refund are built in Phase 8 | `docs/decisions/0041-mock-provider-checkout-refund-phase-8.md` | G25; OA-48 |
| ADR-0042 | A checkout whose expected total no longer matches is refused with the fresh totals | `docs/decisions/0042-checkout-expected-total.md` | G4; OA-49 |
| ADR-0043 | Refunds are payment records: a partial refund keeps the order state, and a refund can be recorded after a terminal state | `docs/decisions/0043-refunds-are-payment-records.md` | G26, G27; OA-50, OA-51 |
| ADR-0044 | A failing webhook row is retried 10 times, and a notification timestamp is fresh within the tolerance on both sides | `docs/decisions/0044-webhook-retry-cap-and-clock-skew.md` | G7, G8; OA-53 |
| ADR-0045 | The inline webhook budget is 2000 ms | `docs/decisions/0045-webhook-inline-budget.md` | OA-54 |
| ADR-0046 | A voucher for an expired order is cancelled at the provider, and the order stays expired | `docs/decisions/0046-late-voucher-is-cancelled.md` | G11; OA-55 |
| ADR-0047 | A webhook and a reconciliation run on one approval move the order once, and the second is a no-op | `docs/decisions/0047-webhook-vs-reconcile-is-a-no-op.md` | G14; OA-56 |
| ADR-0048 | A refund sets the payment's `refunded_cents` to the running total | `docs/decisions/0048-refunded-cents-is-the-running-total.md` | G46; OA-57 |
| ADR-0049 | A cart is converted at checkout (T1), in the order's transaction | `docs/decisions/0049-cart-converted-at-checkout.md` | G22; OA-58 |
| ADR-0050 | A reservation never expires before its order's payment deadline | `docs/decisions/0050-reservation-never-before-payment-deadline.md` | G48; OA-59 |

## Appendix C — Dated market facts

Not normative. These are the plan's figures as of September 2026, USD list prices for AWS in `us-east-1`. Providers change them; re-verify each table at the signup that depends on it (S1, S2, S4).

### C.1 Payment providers (plan 3.4)

| | Mercado Pago (Checkout Pro) | Stripe MX | PayPal MX |
|---|---|---|---|
| Card fee (domestic) | ~3.49 % + MXN 4, + IVA; the rate varies with settlement speed (D13) | 3.6 % + MXN 3.00 per successful domestic-card transaction, excluding IVA | ~3.95 % + MXN 4 (third-party comparison; verify) |
| OXXO cash | Native, included | Bank-based and other methods: 4 % + MXN 3.00 | No |
| SPEI transfer | Native | Yes, same 4 % + MXN 3 tier | No |
| Wallet and installments | Mercado Pago wallet, Mercado Crédito, meses sin intereses | Meses sin intereses from 5 % for 3 months | Limited |
| Hosted checkout (no PCI scope) | Checkout Pro | Stripe Checkout | Yes |

### C.2 Hosting options (plan 3.5)

| Option | Monthly (compute + Postgres) | Operations burden |
|---|---|---|
| AWS Lightsail container service + managed Postgres | ~$25–35 | Low: managed database, flat pricing, bandwidth included |
| AWS ECS Fargate + RDS | ~$55–90 | High: VPC, load balancer, task definitions, security groups |
| Fly.io | Managed Postgres Basic alone $38.00, plus ~$6 compute | Low |
| Railway / Render | ~$25–45 | Low |
| Hetzner + Coolify | ~€6 | High: OS patching, backups and the database are yours |

Lightsail managed databases start at $15 a month for the Micro tier (1 vCPU, 1 GB RAM, 40 GB SSD). New AWS accounts get 3 months free on selected bundles, including the $15 database and the $10 Micro container service.

### C.3 Monthly hosting estimate (plan 20.C)

| Item | Spec | Monthly |
|---|---|---|
| Lightsail container service | Micro (0.25 vCPU, 1 GB) at launch | $10 |
| — upgrade path | Small (0.5 vCPU, 2 GB) once the containers feel tight | ($20) |
| Lightsail managed PostgreSQL | Micro: 1 vCPU, 1 GB RAM, 40 GB SSD | $15 |
| Lightsail object storage | 250 GB bundle | $5 |
| Lightsail CDN distribution | Smallest bundle | $2.50 |
| Route 53 hosted zone | Plus queries | $0.60 |
| Domain | `.com`, amortised | $1.20 |
| Transactional email | Resend free tier (3k a month) or SES | $0–1 |
| Sentry, UptimeRobot, GitHub Actions | Free tiers (Actions is free for a public repository) | $0 |
| Database snapshots and weekly dumps | | ~$1 |
| **Total at launch** | | **≈ $35** |
| **Total with the Small container** | | **≈ $45** |

The first three months cost roughly $10–15, because the container and database bundles are free-tier eligible for new accounts. Set the AWS billing alarm at $80 (S1).

Costs outside this table: Mercado Pago card fees (~3.49 % + MXN 4 + IVA, by settlement speed, D13), the extra fee for meses sin intereses (D7), a fee per chargeback, and shipping labels (S7). At launch volume, payment fees are far larger than the hosting bill, so the fee structure is worth optimising before the infrastructure.

## Appendix D — Effort and sequencing

Effort for one developer working evenings and weekends, with Claude Code doing most of the typing, from plan Appendix E. These are durations of work, not calendar dates. They include writing the tests each phase specifies. Phases 4, 8 and 9 are where the real thinking happens; do not compress them.

| Phases | Theme | Plan effort | Release 1 note |
|---|---|---|---|
| 1 | Repository, tooling and the full test harness | 1–2 weeks | Adds the ADRs, the spec checks and the DS install |
| 2 | Schema | 1 week | Adds the CFDI tables |
| 3 | Catalog and admin | 1–2 weeks | Unchanged |
| 4 | Inventory core | 1–2 weeks — do not rush | Counter sales move to R2; receiving and bin locations are added |
| 5–7 | Public API, accounts, cart | 2–3 weeks | Accounts and pickup move to R2, so expect the lower end |
| 8 | Orders and the state machine | 1–2 weeks — do not rush | R2 transitions deferred; CFDI capture, purchase limits and the cost snapshot added |
| 9 | Payments (mocked): pipeline, simulator, contract suite | 2–3 weeks — do not rush | Unchanged, plus the CFDI review flag |
| 10–11 | Fulfillment (mocked) and email | 1–2 weeks | Pickup and pre-orders move to R2; CFDI tools, exports and DS email vendoring added |
| 12–14 | Storefront: catalog, cart and checkout, account | 3–5 weeks — the weakest area | The DS removes styling work; account pages move to R2 |
| 15 | Local acceptance: demo, journeys, offline clean clone | 1–2 weeks | Four plan journeys plus two new ones; five journeys move to R2 |
| | **Part A total** | **14–24 weeks** | |
| 16 | Mercado Pago integration, sandbox contract run | 1–2 weeks, plus the wait for S2 | Unchanged |
| 17–19 | Email provider and DNS, object storage and CDN, carrier | 1–2 weeks | Unchanged |
| 20–21 | Deployment and operations | 1–2 weeks | Adds the scheduler (G23) |
| 22 | Launch (Release 1) | 1 week | Adds the CFDI routine and the pre-launch switch |
| | **Part B total** | **4–7 weeks** | |

**Overall: 18–31 weeks of effort** in the plan's estimate. The Release 1 cut removes work as well as adding it, so the plan's range still stands, and this spec does not replace it with new figures. It excludes time spent waiting on third parties (S2, S4, S8), on Design System requests, and on deciding the open items in §7.2.

Work that runs alongside the phases (§5): the owner's signups and decisions, and the Design System requests, built in the DS repository. DSR-04 and DSR-05 are needed before Phase 11, and the other Release 1 requests before Phase 12.

## Appendix E — Legacy map

Where each part of `cup-noobles-implementation-plan.md` now lives, and every change made to its tasks and Verify items during the conversion. Plan task numbers and Verify IDs are unchanged unless a row says otherwise.

### E.1 Sections

| Plan | This spec |
|---|---|
| §0 How to use this document | §0.1 (execution protocol), §1.1 |
| §1 Assumptions | §2.3: A1–A14 kept, A1, A8 and A11 rewritten; A15–A19 added |
| §2 Architecture at a glance | §4.1 |
| §3.1–3.5 Technology decisions | §4.2 (ADR-0003 to ADR-0015); dated prices in Appendix C |
| §3.3 rules 1–6 | CR-24 to CR-28 and CR-02; rules 3 and 4 amended (C-01, C-02) |
| §4 Blocking checklist (4.A, 4.B) | §2.4 (S and D items) |
| §5.A Rules | CR-18 to CR-23 |
| §5.B–5.D Interfaces, boundaries, enforcement | §4.3 |
| §5.E Dev defaults | §2.5 |
| §6 consequences 1–3 | CR-37 to CR-39; consequence 1 amended (C-07, OA-03) |
| §6.A Test layers | §4.6 |
| §6.B Coverage gates | §4.6 (Coverage gates), CR-44 |
| §6.C Commands and CI | §0.3 |
| §6.D Traceability | §4.6 (Traceability and the register) |
| §6.E Definition of Done | §0.2 (task report and phase-close report) |
| Phases 1–15 | §6, Phases 1–15; Phase 15 renamed "Local acceptance" |
| Phase 2 canonical DDL | `spec/schema.sql` (§4.4) |
| 2.4 The attribute-agnostic model | §4.4 |
| Phase 4 core rules | CR-04 to CR-08, and kept in Phase 4 |
| 7.3 The cart stores no prices | CR-03, and kept in Phase 7 |
| 8.A, 9.A, 9.B, 9.4, 9.5, 10.A, 11.3, 12.A, 13.A, 14.A, 15.A–15.C, 20.A | Same numbers, inside their phases in §6 |
| Phases 16–22 | §6, Phases 16–22, with their checklists converted to Verify IDs |
| 20.C Monthly cost estimate | Appendix C.3 |
| Appendix A Environment variables | §4.7 |
| Appendix B Cron schedule | §4.8 |
| Appendix C Decision log | §4.2 |
| Appendix D Deliberately not built | §1.3 |
| Appendix E Suggested sequencing | Appendix D |
| Appendix F Design gaps | §2.4 (G1–G22; G2 widened to Phase 4; G6, G9, G10 and G16 deferred to R2) |

### E.2 Changes by phase

#### Phase 1

| Item | Change | Reason |
|---|---|---|
| Phase 1 | New "Bootstrap (owner, before T1.1)" subsection | `/task` needs the spec and skills in the repository first |
| T1.1 | Tree adds `SPEC.md`, `spec/schema.sql`, agent files, `apps/invoicing/`, `docs/decisions/`, `docs/review/`, `infra/crontab`, `check_register.py`, PR template, `web/.npmrc`, `web/pnpm-workspace.yaml`; drops `docs/implementation-plan.md` | §4.4, §4.5, §0.5, A8 |
| T1.3 | Absorbs plan 1.4; adds `INVOICE_PROVIDER` and the dev-tools rule | One session each; §4.3 |
| T1.4 | Absorbed by T1.3 | Same settings file; one session |
| T1.5 | Rewritten: pnpm, the DS layer pinned at 1.0.0, no direct `@nuxt/ui` or `tailwindcss`, no `main.css` | C-01, C-02, C-11; §4.5 |
| T1.6 | Adds the `scheduler` service and an empty `infra/crontab`; build secret for `NODE_AUTH_TOKEN` | plan App. B; §4.5 |
| T1.9 | Moved to the end as the phase-close task; adds superseded-run cancellation, GitHub Packages access, the PR template; branch protection is an owner step | OA-03; §4.5; G29; ADR-0029 |
| T1.11 | Registry adds `INVOICE_IMPLS`; Protocols add `Attachment` and `InvoiceProvider` | §4.3 |
| T1.12 | Split into T1.12a (configuration), T1.12b (concurrency helper and checkers), T1.12c (contract and migration harness) | One session each |
| T1.13 | Split into T1.13a (Vitest) and T1.13b (Playwright harness); axe tags now WCAG 2.2 | One session each; CR-35 |
| T1.14 | Split into T1.14a (Make targets, ratchet) and T1.14b (spec checks); copying the plan to `docs/` is dropped | One session each; §4.6 |
| T1.15 | New: seed ADR-0001 to ADR-0025 | §4.2; OA-12 |
| T1.16 | New: health endpoint per G1's resolution | G1; ADR-0028 |
| P1-V03 | Assertion cites §0.3; the CI half is now P1-V23 instead of Phase 20 | G29; ADR-0029 |
| P1-V09 | "Nuxt welcome page" → "the app's index page" | The app extends the DS layer |
| P1-V10 | "plan fixture" → "spec fixture" | The spec replaces the plan |
| P1-V20 | New: axe WCAG 2.2 AA tags | CR-35 |
| P1-V21 | New: release-aware traceability | §4.6; OA-11 |
| P1-V22 | New: register check | §4.6 |
| P1-V23 | New `[manual]`: CI green and branch protection (from plan Phase 20) | G29; ADR-0029 |

#### Phase 2

| Item | Change | Reason |
|---|---|---|
| Phase 2 | Deliverable: migrations match `spec/schema.sql`; the DDL block moved out of the phase | §4.4 |
| Phase 2 "How to build it" | Keeps plan 2.2's rule as phase text; adds the note on deciding the R1 schema items before T2.1a | §4.4 (pending schema changes) |
| Plan 2.4 | Not a task; its text is in §4.4 | Plan heading inside the task numbering |
| T2.1 | Split into T2.1a (customer, catalog), T2.1b (inventory, geography, address, shipping, cart), T2.1c (orders, payments, invoicing, fulfillment, outbox) | One session each |
| T2.1c | Adds `invoice_request` and `invoice_document` | A8; §4.4 |
| T2.2 | Absorbed by T2.1a–T2.1c; its rule stays in "How to build it" | Each sub-task writes its own `RunSQL` |
| T2.3 | Absorbed by T2.1a | `AUTH_USER_MODEL` must be set in the first migration |
| T2.6 | Absorbed by T3.4 | Same widget (plan 3.4 says "from 2.6") |
| T2.7 | Seeds the warehouse `almacen` (`kind='warehouse'`, not a pickup point) instead of the store `tienda` | D4; CR-47; §2.5 |
| T2.8 | Seeds five types, adding `accessory`; each schema carries the `[PLACEHOLDER]` comment; `board_game` and `accessory` get empty schemas | D14 stand-in; §2.5 |
| T2.9 | New: `check_placeholders` and the `cfdi_catalogs.json` sample; phase-close task | §2.5; D16; REQ-065 |
| Task order | T2.7 and T2.8 run before T2.5 (P2-V14 needs the launch schemas) | Dependencies |
| P2-V01 | Parses `spec/schema.sql` instead of `docs/implementation-plan.md` | §4.4 |
| P2-V14 | "For each launch product type" → "with a non-empty schema" | `board_game` and `accessory` have empty stand-in schemas |
| P2-V15 | "the 4 launch product types" → "the 5 launch product types of the D14 stand-in" | D14 |
| P2-V17 | New: invoice table constraints | REQ-060 |
| P2-V18 | New: `check_placeholders` kinds | REQ-065 |
| Fixtures | `ProductTypeFactory` adds `accessory`; `LocationFactory` defaults to the warehouse (`pickup_point` is R2); adds `InvoiceRequestFactory`; `canonical_ddl` reads `spec/schema.sql` | D14; CR-47; A8; §4.4 |

#### Phase 3

| Item | Change | Reason |
|---|---|---|
| Phase 3 deliverable | "the developer" → "the owner" | A15: the owner is the developer |
| T3.4 | Absorbs plan 2.6 (the widget's first paragraph comes from 2.6) | Same widget |
| T3.5 | Cross-reference §5.C → §4.3 | Section map |
| T3.6 | Adds: the file path is given at run time; catalog files with costs are never committed | CR-49; CR-48 |
| T3.7 | Phase-close task; cross-reference 15.1 → T15.1 | §0.2 |
| P3-V01 | Owned by T3.3 (it also asserts the admin inline error) | Each ID owned once |

#### Phase 4

| Item | Change | Reason |
|---|---|---|
| Phase 4 | "Release 1 scope" line: counter sales are R2; adds receiving, bin locations and the integrity command | §1.2; OA-11 |
| Core rules | Each rule cites its CR; rule 5 tagged R2 | §2.1; §1.2 |
| T4.1 | `record_in_store_sale` removed (moved to T4.10); pre-order branches in the docstrings tagged R2 | OA-11; §1.2 |
| T4.3 | Adds its `infra/crontab` line | §4.8 |
| T4.5 | Tagged R2; depends on T4.10; notes that the plan has no Verify item for the page | A11 rewritten; every task names its tests |
| T4.6 | Adds the `enqueue_email()` write helper per G2; adds its crontab line | G2 (widened to Phase 4); §4.8 |
| T4.7 | New: "Recibir mercancía" admin action per G20 (R1 part; the pre-order path stays in 10.3) | REQ-064; GE:T30 |
| T4.8 | New: bin location per G34; phase-close task; includes the schema amendment if G34 is decided after Phase 2 | REQ-064; §4.4 |
| T4.9 | New: `check_stock_integrity` built here per G24 (moved from plan 21.7) | G24 |
| T4.10 | New, R2: `record_in_store_sale` (from plan 4.1) | OA-11 |
| P4-V04 | Tagged [R2]; owned by T4.10 | Counter sales are R2 |
| P4-V06 | "all four inventory invariants" → "all its inventory invariants" (the pre-order invariant is R2, §4.6) | §4.6 |
| P4-V07 | Marked ⚠️ G24; owned by T4.9 | G24 |
| P4-V14 | Tagged [R2]; owned by T4.10 | Counter sales are R2 |
| P4-V15 | Reason list drops `sale_in_store` (covered by P10-V11, R2) | Counter sales are R2 |
| P4-V17 | Marked ⚠️ G2 | The outbox write helper depends on G2 |
| P4-V19 | New: receiving action | REQ-064 |
| P4-V20 | New: bin location editable without touching `on_hand` (the packing view part is P10-V26) | REQ-064 |
| Fixtures | `stocked_variant` defaults to the warehouse; `InventoryMachine` notes the R2 extensions | CR-47; §1.2 |

#### Phase 5

| Item | Change | Reason |
|---|---|---|
| Phase 5 deliverable | Adds the pre-launch mode | REQ-062; G32 |
| T5.1 | The `preorder` list filter is R2 (moved to T5.8); "related products" cites G28 | §1.2; G28 |
| T5.3 | R1 payload drops `preorder`, `preorder_release_date` and `pickup_available` (moved to T5.8) | §1.2; OA-08, OA-11 |
| T5.5 | `npm run gen:api` → `pnpm gen:api` | C-11 |
| T5.7 | New: pre-launch mode on the API per G32; phase-close task | REQ-062; R-19 |
| T5.8 | New, R2: pre-order status, release date, `pickup_available` and the `preorder` filter | R2 parts of plan 5.1 and 5.3 |
| P5-V07 | Drops the pre-order case (moved to P5-V16) | Pre-orders are R2 |
| P5-V10 | "cart, auth and order endpoints" → "cart and order endpoints" | Auth endpoints are R2 |
| P5-V14 | Tagged [R2]; owned by T5.8 | Pickup is R2 |
| P5-V15 | New: pre-launch mode on the API | REQ-062 |
| P5-V16 | New [R2]: pre-order status (the R2 case of P5-V07) | Mixed R1/R2 item split |
| Fixtures | `catalog_dataset` notes its pre-order product serves R2 items; adds `prelaunch_on` | §1.2; G32 |

#### Phase 6

| Item | Change | Reason |
|---|---|---|
| Phase 6 | Deliverable and scope rewritten: R1 is 6.2, 6.6 and 6.7b; the rest is R2 | §1.2; OA-11 |
| T6.1 | Tagged R2; depends on the outbox write helper in T4.6 | OA-11; G2 |
| T6.2 | R1; body adds that the R1 session is the staff session and that cart and checkout use the same CSRF scheme | Staff admin and pre-launch (G32) need it; P7-V18 |
| T6.3 | Tagged R2 | OA-11 |
| T6.4 | Tagged R2; the guest-lookup limit moves to T6.7b | OA-11 |
| T6.5 | Tagged R2 | OA-11 |
| T6.6 | Adds `manage.py load_postal_codes`; the "optional SEPOMEX" sentence now points to G30 and P13-V06 | §4.3; G30 |
| T6.7 | Split into T6.7a (customer order history, R2) and T6.7b (guest lookup, R1, phase-close) | Mixed R1/R2 task (§1.2) |
| T6.7b | `GET …/lookup/?number=&email=` → `POST /api/orders/lookup/` with a JSON body, per G35's proposal; adds `django-ratelimit` | G35 |
| T6.8 | Tagged R2 | OA-11 |
| Task order | Tasks listed in execution order: T6.2, T6.6, T6.7b (R1), then T6.1, T6.3, T6.4, T6.5, T6.7a, T6.8 (R2) | Dependencies; R2 after R1 (OA-42) |
| P6-V01, P6-V02, P6-V03, P6-V04, P6-V05, P6-V06, P6-V07, P6-V08, P6-V09, P6-V10, P6-V12, P6-V15, P6-V17 | Tagged `[R2]` | Customer accounts are R2 (§1.2) |
| P6-V05 | Tagged `[R2]`; the R1 CSRF check is P7-V18 | Addresses are R2 |
| P6-V11 | Tagged `[R2]`; the guest-lookup case removed and moved to P6-V18 | Mixed R1/R2 item |
| P6-V14 | Marked ⚠️ G35 | The lookup follows G35's proposal |
| P6-V18 | New: guest-lookup rate limit (pre-allocated) | R1 part of P6-V11 |
| Fixtures | Customer fixtures marked Release 2 | OA-11 |

#### Phase 7

| Item | Change | Reason |
|---|---|---|
| Phase 7 | Deliverable and scope: delivery only in R1; merge on login, pickup and pre-orders are R2 | §1.2; OA-08, OA-11 |
| Phase 7 | Tasks listed in execution order: T7.9, T7.7, T7.2a, T7.1, T7.3, T7.4, T7.6, T7.5a, T7.8, then the R2 tasks | Totals and quotes are needed before the endpoints that use them |
| T7.1 | `POST /api/cart/fulfillment/` accepts only `delivery` in R1; it is wired to the quote in T7.6; CSRF note added | OA-08; P7-V18 |
| T7.2 | Split into T7.2a (cart token cookie, R1) and T7.2b (merge on login, R2) | Mixed R1/R2 task |
| T7.4 | `preorder` status moves to R2 | Pre-orders are R2 |
| T7.5 | Split into T7.5a (lines without shipping, R1) and T7.5b (mixed carts and pickup, R2) | Mixed R1/R2 task |
| T7.6 | Wires the fulfillment endpoint; the pickup sentence is marked R2 | Scope moved from T7.1 so the endpoint and its service land together |
| T7.7 | §5.E → §2.5; D5 stand-in noted | Spec references |
| T7.8 | Adds the `infra/crontab` line; phase-close | §4.8 |
| P7-V01, P7-V07, P7-V12, P7-V13, P7-V14 | Tagged `[R2]` | Login, pickup and pre-orders are R2 |
| P7-V04 | "§5.E dev defaults" → "§2.5 dev defaults" | Spec references |
| P7-V17 | "from §6.A" → "The R1 totals and IVA properties from §4.6 (the pickup property joins in R2)" | Pickup is R2 |
| P7-V18 | New: CSRF on cart writes (pre-allocated) | R1 replacement for P6-V05 |
| Fixtures | `dev_defaults` seeds the warehouse location | D4; CR-47 |

#### Phase 8

| Item | Change | Reason |
|---|---|---|
| Phase 8 | Deliverable and scope rewritten for R1 (delivery transitions; invoice data; limits; cost snapshot) | §1.2; §5 |
| 8.A | `Release` column added; R1 rows T1, T2, T4–T7, T10–T12, T16 (from `paid`, `preparing`), T17, T18; R2 rows T3, T8, T9, T13–T15, T19 and T16's other sources | §1.2; OA-08, OA-11 |
| 8.A | T1 and T16 side effects marked "see G25"; T17 and T18 guards "see G27"; T18 side effect "see G26"; T17 and T18 gain "flag an issued CFDI for review (T9.14)" | §2.4; A12 |
| 8.A | Closing text: `TRANSITIONS` holds the rows of the release in progress; P8-V07 derives its cases from it | OA-11 |
| T8.1 | Adds a test that `TRANSITIONS` equals the 8.A rows of the release (the table is the test oracle) | §4.6 |
| T8.3 | G5's proposal (store timezone, per-year sequence) stated | G5 |
| T8.10 | New, placed before T8.2: the mock provider's `create_checkout` and `refund` (G25) | G25 |
| T8.2 | Release 1 target is a delivery address in the request; pickup and saved addresses are R2; notes that T8.7–T8.9 add steps | §1.2 |
| T8.4 | R1 body is delivery only with an optional `invoice` object; `address_id` and `pickup_location_id` are R2; G3 and G4 notes | §1.2; G3; G4 |
| T8.7 | New: invoice data at checkout (P8-V19), with the RFC format and catalog check | A8; OA-07; D16 |
| T8.8 | New: purchase limits per customer (P8-V20) | G31; D15 |
| T8.9 | New: unit-cost snapshot (P8-V21) | G33 |
| T8.6 | Split into T8.6a (T5 and T12, R1, phase-close, adds the crontab line) and T8.6b (T14 and T15, R2) | Mixed R1/R2 task |
| T8.11 | New R2 task: the R2 rows of 8.A, pickup and saved-address checkout | Owner for the R2 Verify items |
| Phase 8 | Tasks listed in execution order: T8.1, T8.3, T8.10, T8.2, T8.4, T8.7, T8.8, T8.9, T8.5, T8.6a, then R2 | Dependencies |
| P8-V01 | Edited to the R1 rows; marked ⚠️ G25; R2 rows moved to P8-V22 | Mixed R1/R2 item; G25 |
| P8-V06 | Marked ⚠️ G25 | The refund comes from T8.10 |
| P8-V07 | "absent from 8.A" → "absent from `TRANSITIONS`" | Release-aware table |
| P8-V13 | Edited to the `delivered` case; `picked_up` moved to P8-V23 | Mixed R1/R2 item |
| P8-V17 | Tagged `[R2]` | Pre-orders are R2 |
| P8-V18 | "pickup without a location" removed; moved to P8-V24 | Mixed R1/R2 item |
| P8-V19, P8-V20, P8-V21 | New (pre-allocated) | REQ-060, REQ-061, REQ-063 |
| P8-V22 | New `[R2]`: the R2 rows of 8.A | Split from P8-V01 |
| P8-V23 | New `[R2]`: `picked_up` auto-completion boundary | Split from P8-V13 |
| P8-V24 | New `[R2]`: pickup checkout validation | Split from P8-V18 |
| Fixtures | `order_in_state` pickup and pre-order traits are R2; `transition_table` holds the R1 rows | §1.2 |

#### Phase 9

| Item | Change | Reason |
|---|---|---|
| Phase 9 | Release 1 scope line added: all tasks plus T9.14 | §5 |
| 9.A | Rule 5 cites §4.8 instead of Appendix B; closing line maps the rules to CR-11–CR-16 | Spec references |
| Phase 9 | Tasks listed in execution order: T9.1, T9.2, T9.9, T9.3, T9.4, T9.5, T9.6, T9.15, T9.7, T9.8, T9.14, T9.16, T9.10, T9.11, T9.12a, T9.12b, T9.13a, T9.17, T9.13b | Dependencies (the mock precedes the endpoint that uses it) |
| T9.1 | §5.D → §4.3; interface sentence trimmed ("new relative to the original four methods" dropped) | Spec references |
| T9.3 | Adds `manage.py process_webhooks` and its crontab line; G7 and G8 notes | 9.A rule 5 named the command but no task built it; §4.8 |
| T9.4 | Note that `approved` always fires T2 in R1; T3 is R2 | Pre-orders are R2 |
| T9.5 | "🔒 D6 … §5.E" → "D6 … §2.5"; G11 note | Spec references |
| T9.6 | "order status page" → the order status serializer behind the guest lookup (T6.7b) and the landing pages | Customer accounts are R2 |
| T9.7 | Adds the crontab line; G14 note | §4.8 |
| T9.9 | Notes that T8.10 built `create_checkout` and `refund` | G25 |
| T9.12 | Split into T9.12a (`mock_payments …`) and T9.12b (`webhooks …`) | One session each |
| T9.13 | Split into T9.13a (driver, `MockDriver`, PAY-01–PAY-08; holds the full scenario table) and T9.13b (PAY-09–PAY-19 and P9-V01, phase-close) | One session each |
| T9.14 | New: CFDI review flag on refunds, added to T17/T18 side effects (P9-V22) | A12; REQ-060 |
| T9.16 | New: the cart is converted at checkout (P9-V23) | G22; OA-58; REQ-021 |
| T9.17 | New: tests for the uncovered branches that stopped the Phase 9 coverage ratchet; T9.13b also depends on it | Coverage ratchet; owner answer in chat, 2026-10-26 |
| P9-V04 | Owned by T9.12a (it uses the `drop` command) | Ownership |
| P9-V08 | "from §6.A" → "from §4.6" | Spec references |
| P9-V22 | New (pre-allocated) | REQ-060 |
| P9-V23 | New: cart converted at checkout | G22; OA-58 |
| Fixtures | Adds `issued_invoice_order` | P9-V22 |

#### Phase 10

| Item | Change | Reason |
|---|---|---|
| Phase 10 | Deliverable and scope rewritten for R1: delivery, the CFDI tools, the exports and the packing view; pickup and pre-orders follow in R2 | §1.2; OA-08, OA-11 |
| 10.A | `Release` column added (delivery R1; pickup and pre-order R2); "In-store pickup" → "Pickup"; "walk-in customers" dropped from the critical property, which now cites REQ-013 | §1.2; CR-47 |
| Tasks | Listed in execution order: T10.9, T10.1, T10.11, T10.10, T10.12, T10.13, T10.17, T10.14, T10.15, T10.16 (R1), then T10.5, T10.3, T10.4, T10.6, T10.2, T10.8, T10.7 (R2) | Execution order; R2 after R1 |
| T10.1 | R1; no test of its own (P10-V02 in T10.10 and CAR-01/02 in T10.13 cover it) | Ownership: one task per Verify ID |
| T10.2–T10.8 | Tagged R2 | §1.2 |
| T10.3 | Body adds that the "Recibir mercancía" action (T4.7) calls `receive_preorder_stock` for pre-order variants | G20 |
| T10.4 | Names its job, `refresh_preorder_flags` (§4.8) | §4.8 |
| T10.5 | Open item G36 added (pre-order closing date) | G36 |
| T10.7 | "the admin page from 4.5" → "from T4.5"; depends on T4.10 (`record_in_store_sale`) | Phase 4 split |
| T10.11 | Adds its `infra/crontab` line | §4.8 |
| T10.14 | New: CFDI admin queue and recording, through `providers.invoicer()` and `ManualIssueRequired` | REQ-060; A8; §4.3 |
| T10.15 | New: global-invoice export | REQ-060; GE:T32 |
| T10.16 | New: reporting exports; phase-close task | REQ-063; A19; G33 |
| T10.17 | New: packing view with bin locations | REQ-064; G34 |
| P10-V05–P10-V18, P10-V20–P10-V22 (except V19) | Tagged `[R2]`; assertions unchanged | Pickup, pre-orders and counter sales are R2 |
| P10-V23 | New (pre-allocated): CFDI queue and recording | REQ-060 |
| P10-V24 | New (pre-allocated): global-invoice export | REQ-060 |
| P10-V25 | New (pre-allocated): reporting exports | REQ-063 |
| P10-V26 | New (pre-allocated): packing view bin locations; moved out of P4-V20 | REQ-064 |
| Fixtures | `ready_pickup_order`, `preorder_variant`, `awaiting_stock_orders` tagged R2; `invoice_request`, `cfdi_documents`, `export_rows` added | §1.2; new tests |

#### Phase 11

| Item | Change | Reason |
|---|---|---|
| Phase 11 | Deliverable adds "built from the Design System email components"; R1 scope added | §4.5; OA-09 |
| Tasks | Listed in execution order: T11.4, T11.5, T11.6, T11.3, T11.7, T11.1, T11.2, T11.8 (R1), then T11.9 (R2). `send_outbox` needs a sender and templates before it can be tested | Execution order |
| T11.1 | The outbox write helper moved to T4.6 (G2); this task sends; adds its `infra/crontab` line | G2; §4.8 |
| T11.3 | Templates built on the vendored DS reference layout instead of "MJML or plain responsive HTML"; table gains a `Release` column and the `cfdi_issued` row; T3 and T15 triggers noted as R2 | §4.5; OA-09; A8 |
| T11.4 | `Reply-To` comes from `EMAIL_REPLY_TO`; no test of its own (P11-V08 in T11.5) | §4.7 |
| T11.5 | `FileEmailSender` also writes attachments | §4.3; REQ-060 |
| T11.6 | New: vendor the DS email HTML and `ds-email-manifest.json` | §4.5; REQ-055 |
| T11.7 | New: plain-text counterparts; owns P11-V01, which needs the text part | §4.5; DS:email-layouts.md |
| T11.8 | New: `cfdi_issued` with attachments; phase-close task | REQ-060 |
| T11.9 | New `[R2]`: the five R2 templates and their triggers | §1.2 |
| P11-V01 | "All 11 templates" → "every template of the release in progress" | §1.2 |
| P11-V08 | "the store's monitored inbox" → "`EMAIL_REPLY_TO` (§4.7)" | §4.7 |
| P11-V09 | Edited to the R1 triggers; the R2 triggers moved to P11-V14 | §1.2 |
| P11-V11 | New (pre-allocated): CFDI email with attachments | REQ-060 |
| P11-V12 | New (pre-allocated): templates built from the vendored DS HTML | REQ-055 |
| P11-V13 | New (pre-allocated): complete plain-text part | REQ-055 |
| P11-V14 | New `[R2]` (beyond the pre-allocated list): the R2 triggers removed from P11-V09 | Mixed R1/R2 item split |
| Fixtures | `mailbox` parses attachments; `vendored_ds_email` added | New tests |

#### Phase 12

| Item | Change | Reason |
|---|---|---|
| Phase 12 | Deliverable adds the pre-launch page and "assembled from the Design System layer"; `useAuth` leaves the deliverable (R2) | §1.2; §4.5; G32 |
| 12.A | Home: "pre-orders open" marked R2 (T12.17), "featured" marked G28; a note that every route shows the pre-launch page while the mode is on | §1.2; G28; G32 |
| Tasks | Listed in execution order: T12.1, T12.14, T12.2, T12.11, T12.6, T12.4, T12.5, T12.16, T12.10, T12.13, T12.7, T12.8, T12.9, T12.15, T12.12 (R1), then T12.3, T12.17 (R2) | Execution order; the styling scan runs early |
| T12.1 | `extends` the DS layer; modules drop `@nuxt/ui`; the production SSR route follows G18 | C-11; §4.5; G18 |
| T12.2 | Cookie forwarding serves a staff session in R1 | §1.2; G32 |
| T12.3 | Tagged R2 (owns P12-V08, P12-V22) | Accounts are R2 |
| T12.4 | Built from DS parts per the §4.5 composition map; depends on DSR-01, DSR-02, DSR-03; `PriceDisplay` no longer formats "$1,234.00 MXN" | CR-26; OA-09; G19 decided (ADR-0024) |
| T12.6 | Cites ADR-0024 and CR-30; locale and currency in one file | G19; DS:formatting.md |
| T12.8 | Adds the DS photo standards and DSR-07; no test of its own | DS:ADR-0056, DS:ADR-0057 |
| T12.9 | Focus ring from the DS; tap targets through DS size props | DS:ADR-0009; CR-36 |
| T12.10 | `error.vue` built from the DS error-page pattern; owns P12-V25 | §4.5 |
| T12.12 | Phase-close task | §0.2 |
| T12.14 | New: styling scan and DS pin check | REQ-050; CR-27 |
| T12.15 | New: pre-launch page, with a dev-only toggle `POST /dev/test/prelaunch/` | REQ-062; G32 |
| T12.16 | New: builds the 12.A pages; the plan had no task for them | Gap in the plan's task list |
| T12.17 | New `[R2]`: the home page's open pre-orders | §1.2 |
| Storefront tasks | Done when adds "`/ui-review` ran (§0.5)" | §0.5; OA-13 |
| P12-V08, P12-V22 | Tagged `[R2]` | Accounts are R2 |
| P12-V09 | ⚠️ G19 removed; cites ADR-0024 | G19 decided |
| P12-V13 | Edited to featured products only; the open pre-order moved to P12-V29 | Mixed R1/R2 item split |
| P12-V26 | New (pre-allocated): styling scan | REQ-050 |
| P12-V27 | New (pre-allocated): DS pin check | REQ-050 |
| P12-V28 | New (pre-allocated): pre-launch page | REQ-062 |
| P12-V29 | New `[R2]` (beyond the pre-allocated list): home shows open pre-orders | Mixed R1/R2 item split |
| Fixtures | `staffLogin(page)` and `setPrelaunch(on)` added; seed fixture reference → T1.13b and T15.2 | New tests |

#### Phase 13

| Item | Change | Reason |
|---|---|---|
| Phase 13 | Deliverable: checkout for delivery with an optional CFDI request (pickup is R2); R1 scope added | §1.2; OA-08; A8 |
| 13.A | `/checkout` note: four sections — contact, delivery, invoice (optional), review | REQ-060 |
| Tasks | Listed in execution order: T13.8, T13.1, T13.2, T13.13, T13.5, T13.9, T13.10, T13.3, T13.11, T13.6, T13.12, T13.4, T13.7 (R1), then T13.14 (R2) | Execution order |
| T13.2 | Components built from DS parts per the §4.5 composition map | CR-26; OA-09 |
| T13.3 | No pickup toggle in R1; adds the Factura section; logged-in prefill, pickup and the pre-order notice move to T13.14 | §1.2; REQ-060 |
| T13.6 | Adds G4's `expected_total_cents` handling | G4 |
| T13.7 | Phase-close task; polls through the order-status endpoint (T13.9) and retries through T13.10 | G21, G22 |
| T13.8 | Moved first; no test of its own (used by P13-V02, P13-V18; P15-V11 checks production) | Execution order |
| T13.9 | New (pre-allocated): order-status token endpoint | G21 |
| T13.10 | New (pre-allocated): pay-retry endpoint | G22 |
| T13.11 | New (pre-allocated): "Quiero factura"; adds `GET /api/invoicing/cfdi-catalogs/` if T8.7 doesn't expose the catalog | REQ-060; D16 |
| T13.12 | New (pre-allocated): purchase-limit message | REQ-061; G31 |
| T13.13 | New (beyond the pre-allocated list): the `/carrito` page; the plan had no task for it | Gap in the plan's task list |
| T13.14 | New `[R2]` (beyond the pre-allocated list): pickup, the mixed-cart notice and the logged-in prefill | §1.2 |
| Storefront tasks | Done when adds "`/ui-review` ran (§0.5)" | §0.5; OA-13 |
| P13-V01 | Edited to the delivery purchase; the pickup purchase moved to P13-V25 | Mixed R1/R2 item split |
| P13-V11 | "§5.E dev defaults" → "§2.5 dev defaults" | Spec references |
| P13-V12, P13-V22 | Tagged `[R2]` | Pickup and pre-orders are R2 |
| P13-V23 | New (pre-allocated): "Quiero factura" | REQ-060 |
| P13-V24 | New (pre-allocated): purchase-limit message | REQ-061 |
| P13-V25 | New `[R2]` (pre-allocated): pickup purchase on mobile | Mixed R1/R2 item split |
| P13-V26 | New (pre-allocated): order-status token API ⚠️ G21 | G21 |
| P13-V27 | New (pre-allocated): pay-retry API ⚠️ G22 | G22 |
| Fixtures | `checkoutAs` gains `invoice?`, `fulfillment` becomes an R2 option; `status_token(order)` added | §1.2; new tests |

#### Phase 14

| Item | Change | Reason |
|---|---|---|
| Phase 14 | Deliverable split into the R1 part (`/rastrear`) and the R2 part (accounts) | §1.2; OA-11 |
| 14.A | Adds a `Release` column; only `/rastrear` is R1 | §1.2 |
| T14.6 | R1, listed first as the phase-close task; calls the lookup per G35; shows status as a DS badge instead of a timeline | §1.2; G35; DSR-08 is R2 |
| T14.1 | Tagged R2 | Accounts are R2 |
| T14.2 | Tagged R2; built from DS parts and depends on DSR-08 instead of "Nuxt UI as the base" | CR-26; DSR-08 |
| T14.3 | Split into T14.3a (login, logout, guard redirect) and T14.3b (registration, verification, reset, claiming); both R2 | One session each |
| T14.4 | Tagged R2 | Accounts are R2 |
| T14.5 | Tagged R2; owns the account-pages axe spec P14-V10 | Last account page |
| P14-V01–V08, P14-V11–V16 | Tagged `[R2]` | Accounts are R2 |
| P14-V09 | Stays R1 | `/rastrear` is R1 |
| P14-V10 | Edited to the R2 routes of 14.A and tagged `[R2]` | Its `/rastrear` part moves to P14-V17 |
| P14-V17 | New: axe on `/rastrear` | The R1 part of P14-V10 |
| Fixtures | `loginAs` tagged R2; `readLatestEmail` stays | Accounts are R2; the CFDI and order emails use it in R1 |

#### Phase 15

| Item | Change | Reason |
|---|---|---|
| Phase 15 | Renamed "Local acceptance"; opening paragraph rewritten for R1 (adds CFDI and pre-launch; pickup, pre-orders, counter sales and accounts are R2) | C-06; §1.2 |
| 15.A–15.C, Exit criterion | Moved before the task list as normative subsections | Spec format |
| 15.A | Store row → warehouse `almacen`, not a pickup point; product types → the 5 D14 stand-in types; new `[DEMO] Fundas para cartas` (accessory); `[DEMO] Playera` used by J10 and J11; new guest order history row; `[DEMO] Juego de mesa`, `[DEMO] Figura preventa` and the customer account tagged `[R2]` | CR-47; D14; §1.2 |
| 15.B | New step 9 (CFDI) and step 10 (pre-launch); plan steps 9 and 10 become steps 11 and 12 `[R2]`; plan step 11 (login) becomes step 13 (`/rastrear` in R1, login in R2); plan step 12 becomes step 14; step 1 drops the open pre-order | §1.2; REQ-060; REQ-062 |
| 15.C | Text kept; the journey table is now the first Verify table | Spec format |
| T15.5 | Moved last as the phase-close task; notes the DS package install as part of the only network step | §4.5 |
| T15.6 | Split into T15.6a (J1, J3, J4), T15.6b (J8, J10, J11) and T15.6c `[R2]` (J2, J5, J6, J7, J9) | One session each; §1.2 |
| T15.8 | Notes that `check_placeholders` is built in T2.9 | P2-V18 |
| P15-V02, V05, V06, V07, V09 | Tagged `[R2]` | Pickup, pre-orders, accounts and counter sales are R2 |
| P15-V10 | Checks the R1 steps of the demo script | R2 steps need R2 features |
| P15-V14 | "MVP exit criterion" → "local acceptance exit criterion" | C-06 |
| P15-V15 | New: J10, CFDI requested, issued and emailed | REQ-060 |
| P15-V16 | New: J11, pre-launch until go-live | REQ-062 |
| Fixtures | Adds the sample CFDI documents | J10 |

#### Phase 16

| Item | Change | Reason |
|---|---|---|
| Phase 16 | Opens Part B with a short intro paragraph; acceptance criterion now names P16-V01 | Spec format; REQ-041 |
| T16.1 | Owner performs the dashboard steps; the agent lists them | §0.1 step 12 |
| T16.2 | `back_urls` note on the G21 status token; installments read `PAYMENT_INSTALLMENT_OPTIONS` | G21; §4.7 |
| T16.6 | Adds that adapter tests needing a vendor SDK also carry `sandbox`, and import the adapter inside the test so traceability still collects them | CR-23; §4.6 |
| T16.7 | Phase-close task; owns P16-V01 and the manual browser purchase | §0.2 |
| Verify | The plan's checklist becomes P16-V01, P16-V02, P16-V03 `[manual]`; "Part A suite unchanged with mock" is covered by P9-V01 in `make test-all`, no new ID | §4.6 |
| P16-V01 | New: sandbox contract run (cited by REQ-041) | Plan checklist item 1 |
| P16-V02 | New: `prod.py` starts with `mercadopago` (refusing `mock` is P1-V14) | Plan checklist item 4 |
| P16-V04 | New: preference payload | 16.2 |
| P16-V05 | New: status mapping on captured responses | 16.3 |
| P16-V06 | New: signature verification on captured notifications | 16.4 |
| P16-V07 | New: refunds, cash raises `RefundNotSupported` | 16.5 |
| P16-V03 | New `[manual]`: browser purchase through Checkout Pro | Plan checklist item 3 |

#### Phase 17

| Item | Change | Reason |
|---|---|---|
| T17.1 | Now the adapter only; adds attachments, `reply_to` and the error mapping to its scope | §4.3; REQ-060 |
| T17.2 | New: sending domain, DNS records, `DEFAULT_FROM_EMAIL` and `EMAIL_REPLY_TO`; owner adds the records | Plan 17.1's DNS half; one session each; §0.1 step 12 |
| P17-V01 | New: adapter request with attachments | REQ-060; §4.3 |
| P17-V02 | New: provider errors map to `EmailSendError` | 11.1 |
| P17-V03 | New `[manual]`: rendering in Gmail, Outlook and a phone | Plan checklist item 1 |
| P17-V04 | New `[manual]`: native-speaker copy review, against DS voice and microcopy | Plan checklist item 2; CR-32 |
| P17-V05 | New `[manual]`: mail-tester score | Plan checklist item 3 |

#### Phase 18

| Item | Change | Reason |
|---|---|---|
| T18.1 | Notes that app code keeps using `providers.media_store()` | §4.3 |
| T18.2 | Adds: `backups/` is private; CFDI documents never go to object storage; the owner performs console steps | §4.4; 21.5; §0.1 step 12 |
| T18.3 | `none` provider without `CDN_BASE_URL`, CDN provider with it | §4.3 |
| P18-V01 | New: S3 storage settings, no SDK import | 18.1; CR-19 |
| P18-V02 | New: image provider selection | 18.3 |
| P18-V03 | New `[manual]`: derivatives in object storage | Plan checklist item 1 |
| P18-V04 | New `[manual]`: CDN cache hit | Plan checklist item 2 |
| P18-V05 | New `[manual]`: only the image prefix is public | Backups (21.5) and fiscal data must stay private |

#### Phase 19

| Item | Change | Reason |
|---|---|---|
| Phase 19 | Acceptance criterion names P19-V01 | REQ-041 |
| T19.4 | Phase-close task; notes the suite runs offline in `make test-all` | No SDK or network needed |
| Verify | Checklist converted; "Part A suite still passes with mock" is covered by P10-V01, no new ID | §4.6 |
| P19-V01 | New: carrier suite with `ManualDriver`, only CAR-04 and CAR-05 skipped (cited by REQ-041) | Plan checklist item 1 |
| P19-V02 | New: tracking URL template, `TrackingNumberRequired`, `UNKNOWN` status, template without `{tracking}` rejected at startup | 19.2; §4.7 |
| P19-V03 | New: missing tracking number is a field error | Plan checklist item 3 |
| P19-V04 | New `[manual]`: real tracking page opens | Plan checklist item 2 |

#### Phase 20

| Item | Change | Reason |
|---|---|---|
| 20.A | Adds the `scheduler` row, marked as G23's proposal | G23; §4.8 |
| 20.C | Cost table moved to Appendix C (C.3); the phase keeps a pointer and the billing-alarm note | Dated market facts are not normative |
| T20.1 | Notes that the `scheduler` container shares the image and must not run `migrate` | G23; R-07 |
| T20.2 | `npm ci` → pnpm with `NODE_AUTH_TOKEN` as a build secret | §4.5; C-11 |
| T20.3 | Secrets appear only as `${VAR}` placeholders | CR-50 |
| T20.4 | Absorbed by T1.16 and T20.3 | G1; ADR-0028 |
| T20.5 | The owner creates the secrets; the agent lists them | §0.1 step 12 |
| T20.6 | Moved last as the phase-close task; the smoke step also checks the HTTP redirect and HSTS; D1 listed as blocking | §0.2; plan checklist; §7.2 |
| T20.9 | Struck: recorded as ADR-0015 | It is a decision, not a task |
| T20.10 | New: production scheduler per G23's proposal | G23 |
| Verify | Plan items "CI green on main" and "branch protection" → P1-V23 (Phase 1) | G29; ADR-0029 |
| P20-V01 | New: container spec parsed | 20.3; CR-50 |
| P20-V02 | New: Dockerfiles checked statically | 20.1, 20.2; §4.5 |
| P20-V03 | New: HTTPS and HSTS smoke step in `deploy.yml` (automated version of the plan's HTTPS item) | Plan checklist |
| P20-V04–V08 | New `[manual]`: deploy within 10 minutes, blocked bad deploy, rollback, database not public, billing alarm | Plan checklist |
| P20-V09 | New: scheduler container and `infra/crontab` match §4.8 ⚠️ G23 | G23; §4.8 as the oracle |

#### Phase 21

| Item | Change | Reason |
|---|---|---|
| T21.3 | The owner creates the monitors; the agent lists them | §0.1 step 12 |
| T21.4 | Digest adds CFDI requests waiting and refunded invoiced orders to review | REQ-060; R-17 |
| T21.5 | `pg_backup` saves through `providers.media_store()` under the private `backups/` prefix and adds its crontab line; the image includes the PostgreSQL client tools | §4.3; T18.2; §4.8 |
| T21.7 | Absorbed by T4.9 | G24's proposed resolution |
| T21.8 | Phase-close task; RUNBOOK adds receiving goods and the CFDI routine; counter-sale routines move to R2 | §1.2; REQ-060; REQ-064 |
| P21-V01–V05 | New `[manual]`: Sentry event, uptime alert, digest from production, restore practised, integrity on production data | Plan checklist |
| P21-V06 | New: digest contents | 21.4 |
| P21-V07 | New: JSON logging | 21.2 |
| P21-V08 | New: `pg_backup` round trip | 21.5 |

#### Phase 22

| Item | Change | Reason |
|---|---|---|
| Phase 22 | Renamed "Launch (Release 1)"; the checklist becomes Verify IDs owned by five new tasks | §0.2; §4.6 |
| T22.1 | New: legal pages, business details, confirmed CFDI catalog | Plan checklist "Legal and business"; D16 |
| T22.2 | New: payments go live | Plan checklist "Payments" |
| T22.3 | New: launch data | Plan checklist "Data" |
| T22.4 | New: technical readiness | Plan checklist "Technical" |
| T22.5 | New: soft launch | Plan checklist "Soft launch" |
| Checklist "CFDI decision made (D3)" | Replaced by P22-V03 (confirmed fields and codes, routine in the runbook) | D3 decided (OA-07) |
| Checklist "Store location, hours and pickup window (D4)" | Replaced by P22-V12 (warehouse location, never shown as a store) | CR-47; OA-08 |
| Checklist "404 and 500 pages branded and useful" | No new ID: covered by P12-V20 and P12-V25 | Already automated |
| Checklist "Backup restore practised", "Billing alarm armed" | Folded into P22-V16 (P21-V04, P20-V08) | Avoid duplicate IDs |
| Checklist "robots.txt allows crawling" | Automated as P22-V18 | §4.6 |
| P22-V01–V03, V05–V17, V19–V23 | New `[manual]` | Plan checklist |
| P22-V04 | New `[R2]` `[manual]`: pre-order terms (D9) | Pre-orders are R2 |
| P22-V07 | Adds a CFDI request and the review flag on refund | REQ-060 |
| P22-V13 | New: purchase limits configured (D15) | REQ-061 |
| P22-V15 | `check_placeholders` exits 0 on production (cited by REQ-065) | REQ-065 |
| P22-V21 | New: pre-launch mode off, catalog published | REQ-062 |
| P22-V22 | Real-phone order is delivery only in R1 | §1.2 |
