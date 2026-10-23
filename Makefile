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

DC       := docker compose
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

.PHONY: help test test-all e2e check-migrations schema-update coverage-ratchet \
        test-integrations test-sandbox test-all-offline clean-clone-check demo demo-reset \
        lint types register scripts-tests web-unit api-tests api-ci api-slow schemathesis-full \
        migration-roundtrip e2e-all lighthouse coverage-report coverage-gates \
        coverage-ratchet-check traceability

help:
	@echo "make test | e2e FILES=... | check-migrations | test-all [PHASE_CLOSE=1] | test-integrations"
	@echo "make test-sandbox | schema-update | coverage-ratchet | test-all-offline | clean-clone-check"
	@echo "make demo | demo-reset"

# --- The commands -----------------------------------------------------------------------------

test: lint types register scripts-tests api-tests web-unit coverage-report
	@echo "make test: green"

test-all: lint types register scripts-tests web-unit \
          api-ci api-slow schemathesis-full migration-roundtrip check-migrations \
          e2e-all lighthouse coverage-report coverage-gates coverage-ratchet-check traceability
	@echo "make test-all: green"

e2e:
	@test -n "$(FILES)" || { echo "usage: make e2e FILES=e2e/p1_smoke.spec.ts"; exit 2; }
	@$(STEP) "playwright $(FILES)" sh -c 'cd web && pnpm exec playwright test $(FILES)'

check-migrations:
	@$(STEP) "makemigrations --check" $(API_TEST) python manage.py makemigrations --check --dry-run

schema-update:
	@$(STEP) "openapi snapshot" $(API_TEST) python manage.py spectacular --validate --fail-on-warn --file openapi.snapshot.yml
	@$(STEP) "api.d.ts" sh -c 'mkdir -p web/app/types && cd web && pnpm exec openapi-typescript ../api/openapi.snapshot.yml -o app/types/api.d.ts'

coverage-ratchet:
	@$(STEP) "coverage baseline" $(API) $(RATCHET) --update

test-integrations:
	@$(STEP) "integrations group" $(API) uv sync --frozen --group integrations
	@$(STEP) "pytest integrations" sh -c '$(API) pytest -q -m integrations; s=$$?; [ $$s -eq 5 ] && echo "no tests marked integrations yet" && exit 0; exit $$s'

test-sandbox:
	@$(STEP) "integrations group" $(API) uv sync --frozen --group integrations
	@$(STEP) "pytest sandbox" $(API) pytest -q -m sandbox --force-enable-socket

test-all-offline:
	@$(DC) build
	@test -f docker-compose.offline.yml || { echo "docker-compose.offline.yml arrives with T15.5; the offline run cannot be checked until then"; exit 1; }
	@COMPOSE_FILE=docker-compose.yml:docker-compose.offline.yml $(MAKE) test-all

clean-clone-check:
	@dir=$$(mktemp -d) && git clone --quiet . "$$dir" && cd "$$dir" && $(MAKE) test-all-offline

demo:
	@$(DC) up -d --wait
	@$(DC) exec -T api python manage.py seed_demo --reset
	@echo "Storefront: http://localhost:8080/   Admin: http://localhost:8080/admin/"

demo-reset:
	@$(DC) exec -T api python manage.py seed_demo --reset

# --- Steps ------------------------------------------------------------------------------------

lint:
	@$(STEP) "lint (ruff, eslint, prettier, markdownlint)" sh scripts/lint.sh

types:
	@$(STEP) "mypy" $(API) mypy .
	@$(STEP) "vue-tsc" $(WEB) pnpm typecheck

register:
	@if [ -f scripts/check_register.py ]; then $(STEP) "register check" $(API) python /repo/scripts/check_register.py; else $(SKIP) "register check" "arrives with T1.14b"; fi

scripts-tests:
	@$(STEP) "scripts tests" $(API) python -m pytest -q -c /repo/scripts/pytest.ini -p no:django /repo/scripts/tests

web-unit:
	@$(STEP) "vitest" $(WEB) pnpm exec vitest run --coverage --coverage.reporter=json-summary --coverage.reporter=text-summary $(WEB_THRESHOLDS)

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
	@$(STEP) "playwright (all specs, axe)" sh -c 'cd web && pnpm exec playwright test'

lighthouse:
	@if [ -f web/lighthouserc.json ]; then $(STEP) "lighthouse budgets" sh -c 'cd web && pnpm exec lhci collect && pnpm exec lhci assert'; else $(SKIP) "lighthouse budgets" "arrives with T12.12"; fi

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
	  $(STEP) "collect playwright names" sh -c 'cd web && pnpm exec playwright test --list > ../var/names-playwright.txt' && \
	  $(STEP) "traceability $(RELEASE)" $(API) python /repo/scripts/check_traceability.py --release $(RELEASE) \
	    --through-phase $(TRACE_THROUGH) --names /repo/var/names-pytest.txt /repo/var/names-scripts.txt /repo/var/names-vitest.txt /repo/var/names-playwright.txt; \
	else $(SKIP) "traceability $(RELEASE)" "arrives with T1.14b"; fi
