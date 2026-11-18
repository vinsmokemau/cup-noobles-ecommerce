"""G83: outside CI the Lighthouse step warns about a score below budget and nothing else
(SPEC.md §2.4; G64, ADR-0073). Any other failure fails the step, on CI and off it."""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "lighthouse_step.sh"
WARNING = "WARNING: lighthouse below budget on this machine"

# What Vitest prints when `lhci assert` finds a page under its budget: the message of
# web/tests/perf/lighthouse.test.ts, then lhci's own report (@lhci/cli, src/assert/assert.js).
BELOW_BUDGET = """\
 FAIL  tests/perf/lighthouse.test.ts > Lighthouse budgets > p12_v02 lighthouse budgets
Error: lhci assert failed

Checking assertions against 3 URL(s), 9 total run(s)

1 result(s) for http://localhost:8081/ :

  X  categories.performance failure for minScore assertion
        expected: >=0.85
           found: 0.82
      all values: 0.82, 0.78, 0.81

Assertion failed. Exiting with status code 1.
"""

# The failure of the first CI run of T15.5: the test file did not even load.
NOT_LOADED = """\
 FAIL  tests/perf/lighthouse.test.ts [ tests/perf/lighthouse.test.ts ]
Error: Transform failed with 1 error:
[TSCONFIG_ERROR] Failed to load tsconfig '.nuxt/tsconfig.app.json': Tsconfig not found
"""

# `lhci assert` ran and failed, but not on a score: it had nothing to judge.
NOTHING_TO_JUDGE = """\
Error: lhci assert failed

Error: No assertions to use
"""

NOT_ANSWERING = """\
AssertionError: the production storefront answers on port 8081: expected undefined to be true
"""


def step(output: str, status: int, ci: str | None) -> subprocess.CompletedProcess:
    """Runs the script around a command that prints `output` and exits with `status`."""
    env = {key: value for key, value in os.environ.items() if key != "CI"}
    if ci is not None:
        env["CI"] = ci
    command = 'printf "%s" "$LH_OUTPUT"; exit "$LH_STATUS"'
    return subprocess.run(
        ["sh", str(SCRIPT), "sh", "-c", command],
        env={**env, "LH_OUTPUT": output, "LH_STATUS": str(status)},
        capture_output=True,
        text=True,
        check=False,
    )


def test_g83_a_passing_step_passes_and_shows_its_output():
    result = step("3 pages within budget\n", 0, None)
    assert result.returncode == 0
    assert "3 pages within budget" in result.stdout
    assert WARNING not in result.stdout


def test_g83_outside_ci_a_score_below_budget_is_a_warning():
    result = step(BELOW_BUDGET, 1, None)
    assert result.returncode == 0
    assert result.stdout.rstrip().splitlines()[-1].startswith(WARNING)
    # The report stays in the output, so the warning says which score.
    assert "found: 0.82" in result.stdout


@pytest.mark.parametrize(
    "output",
    [NOT_LOADED, NOTHING_TO_JUDGE, NOT_ANSWERING, ""],
    ids=["not loaded", "nothing to judge", "not answering", "no output"],
)
def test_g83_outside_ci_any_other_failure_fails_the_step(output):
    result = step(output, 1, None)
    assert result.returncode == 1
    assert WARNING not in result.stdout
    assert output in result.stdout


def test_g83_the_exit_status_of_a_failure_is_kept():
    assert step(NOT_LOADED, 3, None).returncode == 3
    assert step(NOT_LOADED, 3, "false").returncode == 3


def test_g83_on_ci_a_score_below_budget_fails():
    result = step(BELOW_BUDGET, 1, "true")
    assert result.returncode == 1
    assert WARNING not in result.stdout
