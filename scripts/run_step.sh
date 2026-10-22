#!/usr/bin/env sh
# One Makefile step (SPEC.md §0.3): quiet on success, the whole output on failure.
#   run_step.sh <label> <command...>
#   run_step.sh --skip <label> <reason>
set -u

if [ "$1" = "--skip" ]; then
  echo "skip  $2 ($3)"
  exit 0
fi

label=$1
shift
out=$(mktemp)
trap 'rm -f "$out"' EXIT
start=$(date +%s)

if "$@" >"$out" 2>&1; then
  summary=$(grep -v '^[[:space:]]*$' "$out" | tail -n 1 | cut -c 1-100)
  echo "ok    $label ($(($(date +%s) - start))s) ${summary:+- $summary}"
else
  status=$?
  echo "FAIL  $label (exit $status)"
  cat "$out"
  exit "$status"
fi
