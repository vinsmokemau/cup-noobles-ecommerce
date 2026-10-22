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
