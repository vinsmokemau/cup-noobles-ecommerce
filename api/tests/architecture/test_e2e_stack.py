"""G77 (T15.3): the E2E stack runs no scheduler (SPEC.md §4.8), so no job fires in the middle of a
spec. These tests read the compose files and the Makefile; the running stack is shown in the task
report."""

from pathlib import Path

import yaml

from tests.architecture.test_suite_config import (
    MAKEFILE_CANDIDATES,
    read_makefile,
    rule,
)


def repo_root() -> Path:
    for makefile in MAKEFILE_CANDIDATES:
        if makefile.is_file():
            return makefile.parent
    raise AssertionError(f"no Makefile at any of {MAKEFILE_CANDIDATES}")


def services(name: str) -> dict:
    return yaml.safe_load((repo_root() / name).read_text(encoding="utf-8"))["services"]


def scheduler_profile() -> str:
    (profile,) = services("docker-compose.e2e.yml")["scheduler"]["profiles"]
    return profile


def test_g77_the_e2e_override_puts_the_scheduler_behind_a_profile():
    # The development stack runs it; the override takes it out.
    assert "profiles" not in services("docker-compose.yml")["scheduler"]
    assert scheduler_profile()


def test_g77_nothing_enables_the_scheduler_profile():
    root = repo_root()
    profile = scheduler_profile()
    callers = [
        root / "Makefile",
        root / ".github" / "workflows" / "ci.yml",
        root / "web" / "playwright.config.ts",
        *sorted((root / "scripts").glob("*.sh")),
        *sorted((root / "web" / "e2e").glob("*.ts")),
        *sorted((root / "web" / "tests").rglob("*.ts")),
    ]
    assert len(callers) > 10
    for path in callers:
        assert profile not in path.read_text(encoding="utf-8"), path

    # `--profile "*"` would enable it: the Makefile uses that only to take the stack down.
    every_profile = [line for line in read_makefile().splitlines() if '"*"' in line]
    assert every_profile
    assert all(" down" in line for line in every_profile)


def test_g77_the_e2e_targets_remove_a_running_scheduler_before_they_start_the_stack():
    makefile = read_makefile()
    assert "E2E_NO_SCHEDULER := " in makefile
    assert "rm -sf scheduler" in makefile
    for target in ("e2e", "e2e-all"):
        found = rule(makefile, target)
        assert found is not None
        recipe = found[1]
        assert recipe.index("$(E2E_NO_SCHEDULER)") < recipe.index("up -d --wait")
