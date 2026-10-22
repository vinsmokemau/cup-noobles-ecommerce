"""P1-V06: coverage never decreases (SPEC.md §4.6, CR-44)."""

import json

import coverage_ratchet as ratchet
import pytest


def backend_report(critical: tuple[int, int], rest: tuple[int, int]) -> dict:
    """Covered and total statements for one critical file and one other file."""

    def file(covered: int, total: int) -> dict:
        return {
            "summary": {
                "covered_lines": covered,
                "num_statements": total,
                "covered_branches": 0,
                "num_branches": 0,
            }
        }

    return {
        "files": {
            "apps/orders/state_machine.py": file(*critical),
            "apps/catalog/views.py": file(*rest),
        }
    }


def composables_summary(pct) -> dict:
    return {"total": {m: {"pct": pct} for m in ratchet.COMPOSABLE_METRICS}}


@pytest.fixture
def run(tmp_path):
    """Writes the inputs, runs `main`, and returns its exit code."""

    def go(
        *,
        critical=(96, 100),
        rest=(90, 100),
        composables=85,
        baseline=None,
        head=None,
        extra=(),
    ) -> int:
        backend = tmp_path / "coverage.json"
        summary = tmp_path / "summary.json"
        baseline_path = tmp_path / "coverage-baseline.json"
        head_path = tmp_path / "head.json"
        backend.write_text(json.dumps(backend_report(critical, rest)))
        summary.write_text(json.dumps(composables_summary(composables)))
        if baseline is not None:
            baseline_path.write_text(json.dumps(baseline))
        if head is not None:
            head_path.write_text(json.dumps(head))
        return ratchet.main(
            [
                *("--backend", str(backend)),
                *("--composables", str(summary)),
                *("--baseline", str(baseline_path)),
                *("--head-baseline", str(head_path)),
                *extra,
            ]
        )

    return go


# 96 of 100 critical; 186 of 200 overall
GOOD = {"critical": 96.0, "backend": 93.0, "composables": 85.0}


def test_p1_v06_ratchet_rejects_decrease(run):
    # equal and higher pass
    assert run(baseline=GOOD) == 0
    assert run(baseline=GOOD, critical=(98, 100), rest=(95, 100)) == 0
    # below the baseline, though above its gate
    assert run(baseline={**GOOD, "backend": 95.0}) == 1
    assert run(baseline={**GOOD, "composables": 90.0}) == 1
    # below a gate, whatever the baseline says
    low = {"critical": 90.0, "backend": 90.0, "composables": 85.0}
    assert run(baseline=low, critical=(90, 100), rest=(90, 100)) == 1
    assert run(baseline=GOOD, composables=79) == 1
    # the baseline file itself lowered against HEAD
    assert run(baseline=GOOD, head={**GOOD, "backend": 95.0}) == 1
    # no baseline at all
    assert run() == 1


def test_gates_and_ratchet_can_run_apart(run):
    low = {"critical": 90.0, "backend": 90.0, "composables": 85.0}
    kwargs = {"baseline": low, "critical": (90, 100)}
    assert run(**kwargs, extra=["--only", "ratchet"]) == 0
    assert run(**kwargs, extra=["--only", "gates"]) == 1
    assert run(**kwargs, extra=["--only", "report"]) == 0


def test_update_writes_a_rise_and_refuses_a_fall(run, tmp_path):
    assert run(baseline={**GOOD, "backend": 50.0}, extra=["--update"]) == 0
    written = json.loads((tmp_path / "coverage-baseline.json").read_text())
    assert written == GOOD
    assert run(baseline={**GOOD, "backend": 99.0}, extra=["--update"]) == 1


def test_empty_scopes_count_as_covered(run):
    assert run(baseline=GOOD, composables="Unknown", extra=["--only", "gates"]) == 0
    assert ratchet.percent(0, 0) == 100.0
    assert ratchet.percent(1, 3) == 33.33
