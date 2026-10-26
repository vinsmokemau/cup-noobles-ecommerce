# Cup Noobles E-commerce

The online store for Cup Noobles: a Django API (`api/`) and a Nuxt storefront (`web/`) behind a Caddy proxy, all run through Docker Compose.

[`SPEC.md`](SPEC.md) is the contract: code is built from it, never the other way around. Work arrives as one task from SPEC.md §6 (see [Working on this repository](#working-on-this-repository)). This README is the only onboarding document besides the spec; keep it current when commands, environment variables or operations change.

## Prerequisites

- Docker with Compose v2.
- `make` and a POSIX shell. On Windows, use Git Bash or WSL.
- A GitHub token with the `read:packages` scope, to read the Design System packages (see below).

## Install the Design System packages

The storefront consumes three private packages from GitHub Packages, pinned at one exact version (SPEC.md §4.5):

- `@vinsmokemau/cup-noobles-nuxt`
- `@vinsmokemau/cup-noobles-tokens` (brought in by the layer)
- `@vinsmokemau/cup-noobles-email`

Every install needs a token:

1. `web/.npmrc` is committed and holds only `@vinsmokemau:registry=https://npm.pkg.github.com`. Do not add a token to it.
2. Add the token line to your user-level `~/.npmrc`, never to the repository:

   ```text
   //npm.pkg.github.com/:_authToken=${NODE_AUTH_TOKEN}
   ```

3. Export the token before building images or installing:

   ```sh
   export NODE_AUTH_TOKEN=<your token>
   ```

Docker builds receive `NODE_AUTH_TOKEN` as a build secret, so it never ends up in an image layer. `docker compose build` passes it for you. A plain `docker build` must pass it explicitly, or the install fails with `401 Unauthorized`:

```sh
docker build --secret id=node_auth_token,env=NODE_AUTH_TOKEN -t cupnoobles-web web/
```

Upgrading the Design System is its own task: it changes the pinned version and runs `make test-all`.

## Start

```sh
sh scripts/install-hooks.sh   # once per clone: enables the pre-commit hook in .githooks/
docker compose up --build --wait
```

The proxy serves everything at <http://localhost:8080>: the storefront at `/`, the API under `/api/`, and the admin under `/admin/`. The health check is `GET /api/health/`.

Every provider (payments, carrier, email, storage) is a mock in development, so the stack makes no outbound connection.

## Migrations

```sh
docker compose run --rm api python manage.py migrate
make check-migrations   # fails if a model change has no migration
```

## Seed

| Command | What it does |
|---|---|
| `docker compose run --rm api python manage.py seed_e2e` | Seeds the end-to-end data and writes `var/e2e/manifest.json`. The E2E stack (`docker-compose.e2e.yml`) runs it for you after migrating. |
| `docker compose run --rm api python manage.py seed_states` | Seeds the 32 states into `mx_state`. Idempotent; production runs it in the deploy step (G41). |
| `docker compose run --rm api python manage.py load_postal_codes [file.csv]` | Loads `mx_postal_code` for the postal-code lookup from a CSV with the columns `postal_code,neighborhood,municipality,state_code` (`#` lines are comments). Never makes a network call. With `POSTAL_CODE_DATASET=sample` and no file it loads the committed sample; `sepomex` needs the file path (G30). Idempotent; needs `seed_states` first. All rows load or none do. |
| `docker compose run --rm api python manage.py seed_dev_defaults` | Seeds the 32 states, the `[PLACEHOLDER]` warehouse `almacen` and the five launch product types, whose schemas carry the `[PLACEHOLDER]` comment, and the `[PLACEHOLDER]` shipping zones `local` and `nacional` with their rates (SPEC.md §2.5). Idempotent. |
| `docker compose run --rm api python manage.py check_placeholders` | Exits non-zero while a §2.5 stand-in remains: a `[PLACEHOLDER]` location, shipping zone or rate; a product-type schema or `api/fixtures/cfdi_catalogs.json` with the `[PLACEHOLDER]` comment; the D6 or D7 settings at their dev defaults. The launch checklist requires exit 0 (REQ-065). |
| `docker compose run --rm api python manage.py import_catalog <file.csv> [--dry-run] [--images-dir <folder>]` | Imports products and variants from a CSV, keyed on SKU, so a second run changes nothing. Columns: `sku,product_slug,product_name,product_type,brand,franchise,categories,price_mxn,options_json,attributes_json,weight_grams,image_urls`; `categories` and `image_urls` take `\|`-separated values, and `image_urls` are file paths under `--images-dir`, never URLs. Any other column, such as a cost, is ignored. One invalid row aborts the whole file and every invalid row is reported. `--dry-run` writes nothing. Imported products stay `draft`. The file path is given at run time; a catalog file that holds costs is never committed (CR-49), and `*.private.csv` is git-ignored as a guard. |
| `docker compose run --rm api python manage.py seed_demo` | Seeds one published `[DEMO]` product per launch type (a six-variant sudadera included), under the fictional "Franquicia Demo". No stock and no images yet. Idempotent; refuses to run unless `DEV_TOOLS_ENABLED`. |
| `docker compose run --rm api python manage.py mock_payments deliver [--once\|--loop]` | Sends the mock payment provider's queued notifications (ids only, signed at send time) to `/api/webhooks/payments/mock/`. `--once` (the default) sends everything queued now; `--loop` keeps watching and sends each one `MOCK_WEBHOOK_DELAY_SECONDS` after it was queued. The `mock-webhooks` service runs the loop through Caddy, so the simulator pages (`/dev/payments/…`) update the order a moment after you press a button. Refuses to run unless `DEV_TOOLS_ENABLED`. |
| `docker compose run --rm api python manage.py mock_payments <command>` | The simulator buttons from the command line. Orders are named by number (`CN-2026-000123`), payments by their `mock_pay_…` id. `approve <order> [--installments N] [--amount-cents X]`, `reject <order>`, `pay-voucher <payment>`, `expire-voucher <payment>`, `drop <order> --outcome approve\|reject\|pending` (records the outcome with no notification, so only `reconcile_payments` finds it), `chargeback <payment>`, `expire-order <order>` (moves the deadline and holds into the past, then runs `expire_reservations`), `list [--order N]`, `reset`. Refuses to run unless `DEV_TOOLS_ENABLED`. |
| `docker compose run --rm api python manage.py webhooks <command> <webhook_event id>` | Re-sends a stored notification, rebuilt from the `webhook_event` row and signed again with the active provider's secret. `replay` (same notification id; a no-op, expects 200), `duplicate --count N [--concurrent]` (removes the stored row, then delivers N times; one is processed, the rest answer 200), `tamper` (corrupted signature; expects 401 and records an unverified row), `stale` (signed older than `WEBHOOK_MAX_AGE_SECONDS`; expects 401). `--base-url` defaults to `SITE_URL`. Refuses to run unless `DEV_TOOLS_ENABLED`. |

The full demo dataset (`seed_demo --reset`, `make demo`) arrives with SPEC.md T15.1. This table grows as tasks land.

## Run the tests

Every target runs inside the compose environment, so local runs and CI use the same images. On success a target prints one line per step; on failure it prints the failing step's full output.

| Command | What it runs |
|---|---|
| `make test` | Linters (ruff, eslint, prettier, markdownlint), mypy and vue-tsc, the register check, pytest without the `slow` and `sandbox` markers, Vitest. Run it for every task. |
| `make e2e FILES=e2e/p1_smoke.spec.ts` | The named Playwright specs on desktop and mobile, with axe, against the E2E stack. |
| `make check-migrations` | `makemigrations --check --dry-run`. |
| `make test-all` | Everything in `make test`, plus the slow tests, the full schemathesis run, the migration round trip, all Playwright specs, the coverage ratchet and the traceability check. Add `PHASE_CLOSE=1` to enforce the coverage gates. |
| `make schema-update` | Regenerates `api/openapi.snapshot.yml` and `web/app/types/api.d.ts` after an intentional API change. |
| `make coverage-ratchet` | Rewrites `coverage-baseline.json` after coverage rises. |

`make help` lists every target. The full list, including the targets that arrive in later phases, is in SPEC.md §0.3.

## Where secrets live

Secrets come only from the environment, never from an image or from Git (CR-50):

- `.env` and `.env.*` are gitignored (`.env.example` is the only exception).
- `NODE_AUTH_TOKEN` reads the Design System packages. Locally it comes from your shell and your user-level `~/.npmrc`. In CI it is `secrets.GITHUB_TOKEN`.
- The values in `docker-compose.yml` (database password, `SECRET_KEY`) are development placeholders, not secrets.
- Real provider credentials belong to the production setup. They are set in the hosting environment and are never committed.

The full list of environment variables is in SPEC.md §4.7. This repository is public: never commit costs, margins, supplier data, a catalog file with costs, or any credential.

## Repository layout

```text
api/        Django API (apps, config, tests, openapi.snapshot.yml)
web/        Nuxt storefront (app, server, e2e, unit tests)
proxy/      Caddyfile: same-origin routing for web and api
infra/      Scheduled jobs (crontab)
scripts/    Make helpers, the register and traceability checks, the coverage ratchet
spec/       schema.sql, the database contract
docs/       decisions/ (ADRs) and review/ (pinned guidelines)
SPEC.md     The contract
```

## Working on this repository

- Work comes as exactly one task from SPEC.md §6, started with `/task <id>` (for example `/task T1.10`). One task per session.
- Decisions only the owner can make go through `/decide`; the answer is recorded in SPEC.md §2.6 and an ADR in `docs/decisions/`.
- Code, docs and the spec are in English. Customer-facing copy is Spanish (es-MX) and follows the Design System.
- `CLAUDE.md` holds the rules for coding agents; `AGENTS.md` is an exact copy of it.
