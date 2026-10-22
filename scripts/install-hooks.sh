#!/usr/bin/env sh
# Point git at the versioned hooks in .githooks/ (run once per clone).
set -eu
cd "$(dirname "$0")/.."
git config core.hooksPath .githooks
echo "git hooks enabled: .githooks/pre-commit"
