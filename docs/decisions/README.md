# Decision records

One file per decision, from the template [`0000-adr-template.md`](0000-adr-template.md). Each record has a context, a decision, its consequences, a status and a source. SPEC.md Appendix B lists the same records; a later decision takes the next number, is written by `/decide`, and is added to both lists in the same commit.

| ADR | Title | Status | Source |
|---|---|---|---|
| [ADR-0001](0001-baseline-assumptions.md) | Baseline assumptions | accepted | §2.3 |
| [ADR-0002](0002-dev-defaults-are-placeholders.md) | Dev defaults are placeholders | accepted | §2.5 |
| [ADR-0003](0003-database-postgresql.md) | Database: PostgreSQL with JSONB | accepted | plan 3.1 |
| [ADR-0004](0004-attribute-model.md) | Attribute-agnostic catalog | accepted | plan 2.4 |
| [ADR-0005](0005-backend-django.md) | Backend: Django and DRF | accepted | plan 3.2 |
| [ADR-0006](0006-background-work-cron.md) | Background work: cron and management commands | accepted | plan 3.2 |
| [ADR-0007](0007-frontend-nuxt-ds-layer.md) | Frontend: Nuxt 4 SSR on the Design System layer | accepted | plan 3.3; C-01, C-02, C-11 |
| [ADR-0008](0008-server-state-only.md) | Client state: server state only | accepted | plan 3.3 |
| [ADR-0009](0009-generated-api-client.md) | API client generated from OpenAPI | accepted | plan 3.3 |
| [ADR-0010](0010-same-origin.md) | One origin through Caddy; session auth | accepted | plan §2 |
| [ADR-0011](0011-server-side-cart.md) | Server-side cart; prices frozen once | accepted | plan 7.3 |
| [ADR-0012](0012-payments-mercado-pago.md) | Payments: Mercado Pago Checkout Pro | accepted | plan 3.4 |
| [ADR-0013](0013-payment-truth.md) | Payment truth: webhook plus reconciliation | accepted | plan 9.A |
| [ADR-0014](0014-preorder-counter.md) | Pre-order stock: a separate counter | accepted | plan 10.A |
| [ADR-0015](0015-hosting-lightsail.md) | Hosting: AWS Lightsail, no staging | accepted | plan 3.5, 20.9 |
| [ADR-0016](0016-integration-adapters.md) | Mock-first integration adapters | accepted | plan §5, 9.9, 9.13 |
| [ADR-0017](0017-test-discipline.md) | Test discipline | accepted | plan §6 |
| [ADR-0018](0018-task-and-phase-gates.md) | Per-task gate and phase-close gate | accepted | OA-03 |
| [ADR-0019](0019-manual-cfdi.md) | CFDI issued by hand in Release 1 | accepted | OA-07 |
| [ADR-0020](0020-release-1-scope.md) | Release 1 scope | accepted | OA-08, OA-11 |
| [ADR-0021](0021-public-repository.md) | Public repository | accepted | OA-10 |
| [ADR-0022](0022-design-system-adoption.md) | Design System adoption | accepted | OA-09, OA-12 |
| [ADR-0023](0023-agent-skills-policy.md) | Agent skills policy | accepted | OA-13 |
| [ADR-0024](0024-price-format.md) | Price format | accepted | G19, C-08 |
| [ADR-0025](0025-brand-assets.md) | Brand assets from the Design System | accepted | D11 |
| [ADR-0026](0026-ds-package-read-access.md) | Read access to the Design System packages | accepted | S8; OA-15 |
| [ADR-0027](0027-prod-settings-mock-rejection.md) | Which values `prod.py` rejects, and the installed apps | accepted | T1.3; OA-16, OA-17 |
| [ADR-0028](0028-health-endpoint-phase-1.md) | Health endpoint in Phase 1 | accepted | G1; OA-20 |
| [ADR-0029](0029-ci-branch-protection-phase-1.md) | CI and branch protection in Phase 1 | accepted | G29; OA-21 |
| [ADR-0030](0030-release-1-schema-additions.md) | Release 1 schema additions | accepted | G3, G5, G28, G31, G33, G34; OA-22 to OA-27 |
| [ADR-0031](0031-fk-delete-rules-in-orm.md) | Foreign key delete rules are enforced by Django | accepted | G40; OA-28 |
| [ADR-0032](0032-seed-states-command.md) | States are loaded in production by a separate seed command | accepted | G41; OA-29 |
| [ADR-0033](0033-import-catalog-all-or-nothing.md) | The catalog importer is all or nothing per file | accepted | G12; OA-31 |
| [ADR-0034](0034-stock-integrity-command-phase-4.md) | The stock integrity command is built in Phase 4 | accepted | G24; OA-33 |
| [ADR-0035](0035-receive-goods-admin-action.md) | Goods are received through an admin action | accepted | G20; OA-34 |

| [ADR-0036](0036-phase-4-open-items.md) | Phase 4 open items: outbox helper, idempotent commit, expiry job, owner alert address | accepted | G2, G15, G37, G38; OA-35 to OA-38 |
| [ADR-0037](0037-public-stock-display.md) | The storefront shows a low-stock badge, with no counts | accepted | D10, G13; OA-40 |
| [ADR-0038](0038-prelaunch-mode-site-setting.md) | Pre-launch mode is a database flag edited in the admin | accepted | G32; OA-41 |
| [ADR-0039](0039-sepomex-launch-requirement.md) | The full SEPOMEX dataset is a launch requirement | accepted | G30; OA-43 |
| [ADR-0040](0040-guest-lookup-post.md) | The guest order lookup is a POST with a JSON body | accepted | G35; OA-44 |
| [ADR-0041](0041-mock-provider-checkout-refund-phase-8.md) | The mock payment provider's checkout and refund are built in Phase 8 | accepted | G25; OA-48 |
| [ADR-0042](0042-checkout-expected-total.md) | A checkout whose expected total no longer matches is refused with the fresh totals | accepted | G4; OA-49 |
| [ADR-0043](0043-refunds-are-payment-records.md) | Refunds are payment records: a partial refund keeps the order state, and a refund can be recorded after a terminal state | accepted | G26, G27; OA-50, OA-51 |
| [ADR-0044](0044-webhook-retry-cap-and-clock-skew.md) | A failing webhook row is retried 10 times, and a notification timestamp is fresh within the tolerance on both sides | accepted | G7, G8; OA-53 |
| [ADR-0045](0045-webhook-inline-budget.md) | The inline webhook budget is 2000 ms | accepted | OA-54 |
| [ADR-0046](0046-late-voucher-is-cancelled.md) | A voucher for an expired order is cancelled at the provider, and the order stays expired | accepted | G11; OA-55 |
| [ADR-0047](0047-webhook-vs-reconcile-is-a-no-op.md) | A webhook and a reconciliation run on one approval move the order once, and the second is a no-op | accepted | G14; OA-56 |
| [ADR-0048](0048-refunded-cents-is-the-running-total.md) | A refund sets the payment's `refunded_cents` to the running total | accepted | G46; OA-57 |
| [ADR-0049](0049-cart-converted-at-checkout.md) | A cart is converted at checkout (T1), in the order's transaction | accepted | G22; OA-58 |
| [ADR-0050](0050-reservation-never-before-payment-deadline.md) | A reservation never expires before its order's payment deadline | accepted | G48; OA-59 |
| [ADR-0051](0051-one-shipment-per-order.md) | An order has at most one shipment | accepted | OA-60 |
