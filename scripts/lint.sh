#!/usr/bin/env sh
# Static style checks (T1.8): ruff, eslint + prettier, markdownlint.
# Run by the pre-commit hook, on the host. `make test` runs the same checks in the compose images
# (the `lint` target of the Makefile): keep the two alike. Run from anywhere.
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)

echo "ruff"
(cd "$root/api" && uv run ruff check . && uv run ruff format --check .)

echo "eslint + prettier"
(cd "$root/web" && pnpm exec eslint . && pnpm exec prettier --check .)

echo "markdownlint"
(cd "$root" && web/node_modules/.bin/markdownlint-cli2 SPEC.md "docs/**/*.md" README.md)
