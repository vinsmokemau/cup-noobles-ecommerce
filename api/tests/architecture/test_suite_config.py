"""P1-V03: `make test-all` runs every layer SPEC.md §0.3 lists for it."""

import re
from pathlib import Path

import pytest

from tests.architecture.ast_scan import API_DIR

# In the api container the repository root is mounted at /repo (docker-compose.yml).
MAKEFILE_CANDIDATES = (Path("/repo/Makefile"), API_DIR.parent / "Makefile")

# What §0.3 says test-all runs, and the Makefile target that runs it.
REQUIRED_STEPS = {
    "ruff, eslint, prettier, markdownlint": "lint",
    "mypy and vue-tsc": "types",
    "the register check": "register",
    "the scripts tests": "scripts-tests",
    "Vitest": "web-unit",
    "pytest without slow, hypothesis ci": "api-ci",
    "the slow tests": "api-slow",
    "full schemathesis": "schemathesis-full",
    "the migration round trip": "migration-roundtrip",
    "makemigrations --check": "check-migrations",
    "all Playwright specs with axe": "e2e-all",
    "Lighthouse budgets": "lighthouse",
    "coverage gates": "coverage-gates",
    "the coverage ratchet": "coverage-ratchet-check",
    "the traceability check": "traceability",
}


# The rest of a rule's first line, including lines continued with a backslash.
PREREQUISITES = r"(?P<pre>(?:[^\n]*\\\n)*[^\n]*)"


def read_makefile() -> str:
    for path in MAKEFILE_CANDIDATES:
        if path.is_file():
            return path.read_text(encoding="utf-8")
    raise AssertionError(f"no Makefile at any of {MAKEFILE_CANDIDATES}")


def rule(makefile: str, target: str) -> tuple[list[str], str] | None:
    """The prerequisites and the recipe of `target`, or None when it has no rule."""
    match = re.search(
        rf"^{re.escape(target)}:{PREREQUISITES}\n(?P<recipe>(?:\t[^\n]*\n?)*)",
        makefile,
        re.MULTILINE,
    )
    if match is None:
        return None
    prerequisites = match["pre"].replace("\\\n", " ").split()
    return prerequisites, match["recipe"]


def missing_steps(makefile: str) -> list[str]:
    """Steps of `test-all` that its prerequisites do not include or that have no rule."""
    found = rule(makefile, "test-all")
    if found is None:
        return list(REQUIRED_STEPS)
    prerequisites, _ = found
    return [
        step
        for step, target in REQUIRED_STEPS.items()
        if target not in prerequisites or rule(makefile, target) is None
    ]


def test_p1_v03_test_all_runs_every_layer():
    assert missing_steps(read_makefile()) == []


def without_prerequisite(makefile: str, target: str, dropped: str) -> str:
    """`makefile` with `dropped` removed from the prerequisites of `target`."""
    match = re.search(
        rf"^{re.escape(target)}:{PREREQUISITES}\n", makefile, re.MULTILINE
    )
    assert match is not None
    start, end = match.span("pre")
    pre = re.sub(rf"(?<![\w-]){re.escape(dropped)}(?![\w-])", "", match["pre"])
    return makefile[:start] + pre + makefile[end:]


def test_each_step_missing_from_test_all_is_reported():
    makefile = read_makefile()
    for step, target in REQUIRED_STEPS.items():
        assert missing_steps(without_prerequisite(makefile, "test-all", target)) == [
            step
        ]


@pytest.mark.parametrize(
    ("target", "needle"),
    [
        ("api-ci", "HYPOTHESIS_PROFILE=ci"),
        ("schemathesis-full", "HYPOTHESIS_PROFILE=ci"),
        ("api-slow", "slow"),
        ("traceability", "--release"),
        ("e2e-all", "playwright test"),
    ],
)
def test_step_recipes_do_what_the_spec_names(target, needle):
    found = rule(read_makefile(), target)
    assert found is not None
    assert needle in found[1]
