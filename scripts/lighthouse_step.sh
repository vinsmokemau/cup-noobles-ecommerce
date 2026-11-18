#!/usr/bin/env sh
# The Lighthouse step of `make test-all` (SPEC.md §0.3; G64, ADR-0073; G83).
#   lighthouse_step.sh <command...>
# Runs the command and prints its output. On CI its exit status stands. Outside CI the machine is
# not steady, so a score below budget is a warning and CI judges it; every other failure (the
# storefront not answering, the test not loading, `lhci collect` failing) still fails the step.
set -u

out=$(mktemp)
trap 'rm -f "$out"' EXIT

"$@" >"$out" 2>&1
status=$?
cat "$out"

[ "$status" -eq 0 ] && exit 0
[ "${CI:-}" = "true" ] && exit "$status"

# A score below budget, and nothing else: the test reached `lhci assert`, its last stage
# (web/tests/perf/lighthouse.test.ts says "lhci assert failed"), and lhci found reports to judge
# and one of them under its budget (lhci says "Assertion failed. Exiting with status code 1.").
if grep -q "lhci assert failed" "$out" &&
  grep -q "Assertion failed\. Exiting with status code 1\." "$out"; then
  echo "WARNING: lighthouse below budget on this machine; CI judges it (ADR-0073)"
  exit 0
fi

exit "$status"
