# The commands of SPEC.md §0.3. Every target prints a short summary per step on success and the
# full output of the failing step only, through scripts/run_step.sh. Steps run in the compose
# environment (docker compose run), so local runs and CI use the same images.
#
# A step whose tooling a later task builds (register check, traceability, Lighthouse) is
# reported as `skip` with the task that adds it, and starts running once its file exists.

SHELL := /bin/sh
.DEFAULT_GOAL := help
.NOTPARALLEL:

# Git Bash on Windows would rewrite /repo and /app into Windows paths.
export MSYS_NO_PATHCONV := 1

# OFFLINE=1 adds docker-compose.offline.yml to every compose command, which makes the project
# network internal: no container reaches the internet (T15.5). Only `make test-all-offline` sets
# it, after it has built and pulled every image and taken the stack down.
OFFLINE ?= 0
ifeq ($(OFFLINE),1)
OFFLINE_FILE := -f docker-compose.offline.yml
DC           := docker compose -f docker-compose.yml $(OFFLINE_FILE)
# Tells web/e2e/p15_offline.spec.ts (P15-V13) that the network is internal, so it runs.
E2E_OFFLINE  := -e E2E_OFFLINE=1
else
OFFLINE_FILE :=
DC           := docker compose
E2E_OFFLINE  :=
endif

API      := $(DC) run --rm -T api
API_TEST := $(DC) run --rm -T -e DJANGO_SETTINGS_MODULE=config.settings.test api
WEB      := $(DC) run --rm -T --no-deps web
STEP     := sh scripts/run_step.sh
SKIP     := sh scripts/run_step.sh --skip

RELEASE ?= R1
# Verify IDs of later phases have no tests yet. `current` checks the phases up to the last one
# whose phase-close task is done; `all` checks the whole release (the final acceptance).
TRACE_THROUGH ?= current
# Set to 1 at the close of a phase to enforce the coverage gates (§0.2, §4.6).
PHASE_CLOSE ?= 0

PYTEST_NOT_SLOW := -m "not slow and not sandbox"
COV             := --cov --cov-report=json:coverage.json
RATCHET         := python /repo/scripts/coverage_ratchet.py --backend /app/coverage.json \
                   --composables /repo/web/coverage/coverage-summary.json \
                   --baseline /repo/coverage-baseline.json \
                   --head-baseline /repo/var/baseline-head.json

# `make test` reports composables coverage; the gate is enforced at phase close.
ifeq ($(PHASE_CLOSE),1)
WEB_THRESHOLDS :=
else
WEB_THRESHOLDS := --coverage.thresholds.lines=0 --coverage.thresholds.branches=0 \
                  --coverage.thresholds.functions=0 --coverage.thresholds.statements=0
endif

.PHONY: help test test-all e2e e2e-reset check-migrations schema-update coverage-ratchet \
        test-integrations test-sandbox test-all-offline clean-clone-check demo demo-reset \
        lint types register scripts-tests web-unit api-tests api-ci api-slow schemathesis-full \
        migration-roundtrip e2e-all lighthouse coverage-report coverage-gates \
        coverage-ratchet-check traceability

help:
	@echo "make test | e2e FILES=... | check-migrations | test-all [PHASE_CLOSE=1] | test-integrations"
	@echo "make test-sandbox | schema-update | coverage-ratchet | test-all-offline | clean-clone-check"
	@echo "make demo | demo-reset | e2e-reset"

# --- The commands -----------------------------------------------------------------------------

test: lint types register scripts-tests api-tests web-unit coverage-report
	@echo "make test: green"

test-all: lint types register scripts-tests web-unit \
          api-ci api-slow schemathesis-full migration-roundtrip check-migrations \
          e2e-all lighthouse coverage-report coverage-gates coverage-ratchet-check traceability
	@echo "make test-all: green"

# Wipes the E2E database volume only (ADR-0070) and starts the E2E stack again, which migrates and
# runs seed_e2e. The development volume `pgdata` is never touched. The stack is one Compose project,
# so `down` also stops the development containers; `docker compose up -d` brings them back.
E2E_DC := docker compose -f docker-compose.yml -f docker-compose.e2e.yml $(OFFLINE_FILE)

# The E2E stack has no scheduler (§4.8, G77): docker-compose.e2e.yml keeps the service behind a
# profile, so `up` never starts it. `up` leaves a running one alone, though, and the development
# stack starts one, so the E2E targets remove it first. `e2e-reset` does it with `down`.
E2E_NO_SCHEDULER := $(STEP) "remove the scheduler (off in the E2E stack)" $(E2E_DC) rm -sf scheduler

# P12-V25 runs as a second Playwright step, after the other specs: its extra storefront server
# takes minutes to answer while they run (G72). PW_MAIN is every other project.
PW_MAIN          := --project=desktop --project=mobile --project=prelaunch --project=prelaunch-mobile --project=selftest
PW_API_DOWN_STEP := $(STEP) "playwright (API down, P12-V25)" sh -c 'cd web && pnpm exec playwright test --project=api-down'

# From Phase 15, `make test-all` runs Playwright and Lighthouse inside the compose network (§4.6),
# in the runner services of docker-compose.e2e.yml: the run needs no browser on the host and works
# with the network internal. A runner has no Docker CLI, so the steps below start and stop what a
# test needs. `make e2e` still runs Playwright on the host.
E2E_RUN     := run --rm -T $(E2E_OFFLINE)
API_DOWN_DC := $(E2E_DC) --profile api-down
LH_DC       := $(E2E_DC) --profile lighthouse
PW_API_DOWN_IN_COMPOSE = $(STEP) "playwright (API down, P12-V25)" sh -c '\
  $(API_DOWN_DC) up -d --wait web-api-down && \
  $(API_DOWN_DC) $(E2E_RUN) e2e-api-down pnpm exec playwright test --project=api-down; s=$$?; \
  $(API_DOWN_DC) stop web-api-down; exit $$s'
# Leaves the exit status in $$s; the storefront's production build is stopped either way.
# Vitest reads web/tsconfig.json, which points at files `nuxt prepare` writes into .nuxt. The runner
# keeps .nuxt in its own volume, empty on a fresh checkout, so the step writes them first.
LH_IN_COMPOSE = $(LH_DC) up -d --wait web-prod proxy-prod && \
  $(LH_DC) $(E2E_RUN) e2e-lighthouse sh -c "pnpm exec nuxt prepare && pnpm exec vitest run tests/perf/lighthouse.test.ts"; s=$$?; \
  $(LH_DC) stop proxy-prod web-prod

# Every image a full run uses, built or pulled now: the only step that needs the network (§0.3).
IMAGES_DC := docker compose -f docker-compose.yml -f docker-compose.e2e.yml \
             --profile e2e --profile api-down --profile lighthouse
# Docker keeps a network as it was created. The stack goes down before the offline run, which then
# creates the network as internal, and after it, so the next `up` gets an ordinary network again.
STACK_DOWN := $(STEP) "stop the stack" $(E2E_DC) --profile "*" down --remove-orphans

e2e-reset:
	@$(STEP) "stop the stack" $(E2E_DC) --profile "*" down --remove-orphans
	@$(STEP) "remove the E2E database volume" docker volume rm -f cupnoobles_pgdata_e2e
	@$(STEP) "start the E2E stack (migrate, seed_e2e)" $(E2E_DC) up -d --wait

e2e:
	@test -n "$(FILES)" || { echo "usage: make e2e FILES=e2e/p1_smoke.spec.ts"; exit 2; }
	@$(E2E_NO_SCHEDULER)
	@$(STEP) "start the E2E stack" $(E2E_DC) up -d --wait
	@$(STEP) "seed_e2e (reset the scarce stock)" $(E2E_DC) exec -T api python manage.py seed_e2e
	@$(STEP) "playwright $(FILES)" sh -c 'cd web && pnpm exec playwright test $(PW_MAIN) $(FILES)'
	@case "$(FILES)" in *p12_errors*) $(PW_API_DOWN_STEP);; esac

check-migrations:
	@$(STEP) "makemigrations --check" $(API_TEST) python manage.py makemigrations --check --dry-run

schema-update:
	@$(STEP) "openapi snapshot" $(API_TEST) python manage.py spectacular --validate --fail-on-warn --file openapi.snapshot.yml
	@$(STEP) "api.d.ts" sh -c 'mkdir -p web/app/types && cd web && pnpm gen:api'

coverage-ratchet:
	@$(STEP) "coverage baseline" $(API) $(RATCHET) --update

test-integrations:
	@$(STEP) "integrations group" $(API) uv sync --frozen --group integrations
	@$(STEP) "pytest integrations" sh -c '$(API) pytest -q -m integrations; s=$$?; [ $$s -eq 5 ] && echo "no tests marked integrations yet" && exit 0; exit $$s'

test-sandbox:
	@$(STEP) "integrations group" $(API) uv sync --frozen --group integrations
	@$(STEP) "pytest sandbox" $(API) pytest -q -m sandbox --force-enable-socket

# The local acceptance exit criterion (15.5, P15-V14): the images first, which is the only step
# that uses the network, then `make test-all` with the project network internal. It stops this
# checkout's stack; `docker compose up -d` brings the development stack back afterwards.
test-all-offline:
	@mkdir -p var
	@$(STEP) "pull the images (network)" $(IMAGES_DC) pull --ignore-buildable
	@$(STEP) "build the images (network)" $(IMAGES_DC) build
	@$(STACK_DOWN)
	@$(MAKE) test-all OFFLINE=1; s=$$?; $(STACK_DOWN); exit $$s

# What the CI job `clean-clone-offline` does, on this machine: a fresh clone of HEAD in a temporary
# directory, with nothing installed on the host and a new E2E database. The clone is its own
# Compose project, so this checkout's stack is stopped first (they would share the E2E database
# volume and the ports). The clone keeps the repository's LF line endings whatever Git is set to
# here. Git is given `.` and this directory, never the temporary path: Git for Windows reads a
# `/tmp/…` argument differently from the shell. On success the clone, its volumes and its images
# are removed (the second `down` takes the development database volume, which the E2E file set
# does not use); a failed clone is kept. The images the clone shares with this checkout by name
# go too, and the next command here builds them again from the cache.
clean-clone-check:
	@$(STACK_DOWN)
	@$(STEP) "remove the E2E database volume" docker volume rm -f cupnoobles_pgdata_e2e
	@dir=$$(mktemp -d) && \
	  (cd "$$dir" && git clone --quiet -c core.autocrlf=false "$(CURDIR)" . && $(MAKE) test-all-offline); s=$$?; \
	  if [ $$s -eq 0 ]; then \
	    (cd "$$dir" && { $(E2E_DC) --profile "*" down --volumes --rmi local --remove-orphans; $(DC) down --volumes; } >/dev/null 2>&1); \
	    rm -rf "$${dir:?}"; echo "make clean-clone-check: green"; \
	  else echo "make clean-clone-check: failed; the clone is kept at $$dir"; fi; exit $$s

# The demo of docs/demo-script.md (15.B) runs on the development stack, never on the E2E one: `up`
# without the E2E override puts `db` on the development volume and starts the scheduler, whose jobs
# send the queued email and move paid orders. `seed_demo --reset` empties that database and the
# var/ stores, and prints the URLs, the staff credentials and the seeded order numbers.
DEMO_SEED  := $(DC) exec -T api python manage.py seed_demo --reset
DEMO_NOTES := echo "Emails:      var/emails/ (files on disk; nothing is sent)"; \
              echo "Demo script: docs/demo-script.md"

demo:
	@$(STEP) "start the development stack" $(DC) up -d --wait
	@$(STEP) "migrate" $(DC) exec -T api python manage.py migrate --noinput
	@$(DEMO_SEED)
	@$(DEMO_NOTES)

demo-reset:
	@$(DEMO_SEED)
	@$(DEMO_NOTES)

# --- Steps ------------------------------------------------------------------------------------

# The linters run in the images, so a clean clone needs no toolchain on the host (T15.5). The
# pre-commit hook runs the same checks on the host, through scripts/lint.sh: keep the two alike.
lint:
	@$(STEP) "ruff" $(API) sh -c 'ruff check . && ruff format --check .'
	@$(STEP) "eslint, prettier" $(WEB) sh -c 'pnpm exec nuxt prepare && pnpm exec eslint . && pnpm exec prettier --check .'
	@$(STEP) "markdownlint" $(WEB) sh -c 'cd /repo && /app/node_modules/.bin/markdownlint-cli2 SPEC.md "docs/**/*.md" README.md'

types:
	@$(STEP) "mypy" $(API) mypy .
	@$(STEP) "vue-tsc" $(WEB) pnpm typecheck

register:
	@if [ -f scripts/check_register.py ]; then $(STEP) "register check" $(API) python /repo/scripts/check_register.py; else $(SKIP) "register check" "arrives with T1.14b"; fi

scripts-tests:
	@$(STEP) "scripts tests" $(API) python -m pytest -q -c /repo/scripts/pytest.ini -p no:django /repo/scripts/tests

web-unit:
	@$(STEP) "vitest" $(WEB) pnpm exec vitest run --exclude 'tests/perf/**' --coverage --coverage.reporter=json-summary --coverage.reporter=text-summary $(WEB_THRESHOLDS)

api-tests:
	@$(STEP) "pytest" $(API) pytest -q $(PYTEST_NOT_SLOW) $(COV)

# make test-all runs the suite in parts, each of which adds to one coverage measurement.
api-ci:
	@$(STEP) "pytest, hypothesis ci" $(API) sh -c 'HYPOTHESIS_PROFILE=ci pytest -q $(PYTEST_NOT_SLOW) --ignore=tests/contract/openapi/test_schemathesis.py $(COV)'

api-slow:
	@$(STEP) "pytest slow" sh -c '$(API) pytest -q -m "slow and not sandbox" --ignore=tests/migrations $(COV) --cov-append; s=$$?; [ $$s -eq 5 ] && echo "no slow tests outside the migration round trip" && exit 0; exit $$s'

schemathesis-full:
	@$(STEP) "schemathesis (ci profile)" $(API) sh -c 'HYPOTHESIS_PROFILE=ci pytest -q tests/contract/openapi/test_schemathesis.py $(COV) --cov-append'

migration-roundtrip:
	@$(STEP) "migration round trip" $(API) pytest -q tests/migrations $(COV) --cov-append

e2e-all:
	@$(E2E_NO_SCHEDULER)
	@$(STEP) "start the E2E stack" $(E2E_DC) up -d --wait
	@$(STEP) "seed_e2e (reset the scarce stock)" $(E2E_DC) exec -T api python manage.py seed_e2e
	@$(STEP) "playwright (all specs, axe)" $(E2E_DC) $(E2E_RUN) e2e pnpm exec playwright test $(PW_MAIN)
	@$(PW_API_DOWN_IN_COMPOSE)

# CI judges the budget; outside CI a score below budget is only a warning (G64, ADR-0073). Any
# other failure fails the step everywhere: scripts/lighthouse_step.sh tells the two apart (G83).
lighthouse:
	@$(STEP) "lighthouse budgets" sh scripts/lighthouse_step.sh sh -c '$(LH_IN_COMPOSE); exit $$s'

coverage-report:
	@$(STEP) "coverage" $(API) $(RATCHET) --only report

coverage-gates:
ifeq ($(PHASE_CLOSE),1)
	@$(STEP) "coverage gates" $(API) $(RATCHET) --only gates
else
	@$(SKIP) "coverage gates" "reported above; enforced with make test-all PHASE_CLOSE=1"
endif

coverage-ratchet-check:
	@git show HEAD:coverage-baseline.json > var/baseline-head.json 2>/dev/null || rm -f var/baseline-head.json
	@$(STEP) "coverage ratchet" $(API) $(RATCHET) --only ratchet

traceability:
	@if [ -f scripts/check_traceability.py ]; then \
	  $(STEP) "collect pytest names" sh -c '$(API_TEST) pytest --collect-only -q > var/names-pytest.txt' && \
	  $(STEP) "collect scripts names" sh -c '$(API) python -m pytest --collect-only -q -c /repo/scripts/pytest.ini -p no:django /repo/scripts/tests > var/names-scripts.txt' && \
	  $(STEP) "collect vitest names" sh -c '$(WEB) pnpm exec vitest list > var/names-vitest.txt' && \
	  $(STEP) "collect playwright names" sh -c '$(E2E_DC) run --rm -T --no-deps e2e pnpm exec playwright test --list > var/names-playwright.txt' && \
	  $(STEP) "traceability $(RELEASE)" $(API) python /repo/scripts/check_traceability.py --release $(RELEASE) \
	    --through-phase $(TRACE_THROUGH) --names /repo/var/names-pytest.txt /repo/var/names-scripts.txt /repo/var/names-vitest.txt /repo/var/names-playwright.txt; \
	else $(SKIP) "traceability $(RELEASE)" "arrives with T1.14b"; fi
