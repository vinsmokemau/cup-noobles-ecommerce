"""P1-V10, P1-V21: every in-scope Verify ID has a collected test (SPEC.md §4.6, REQ-070)."""

import check_traceability as tr
import pytest
import specmd


def spec_with(*rows: str, phase_close_done: bool = False) -> str:
    """A minimal SPEC.md: a Phase 1 table, a Phase 2 table and the phase-close tasks."""
    mark = "x" if phase_close_done else " "
    body = "\n".join(rows)
    return f"""# Fixture

## 3. Requirements

| REQ | Requirement | Rules | Acceptance | Release |
|---|---|---|---|---|
| REQ-900 | A requirement | CR-01 | P1-V01 · P2-V01 [R2] | R1 |

## 6. Task list

### Phase 1 — First

- [x] **T1.1 — One**
  - Release: R1 · Gate: task
  - Verifies: P1-V01

- [{mark}] **T1.9 — Close one**
  - Release: R1 · Gate: phase-close
  - Verifies: P1-V02

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
{body}

### Phase 2 — Second

- [ ] **T2.1 — Two**
  - Release: R1 · Gate: task
  - Verifies: P2-V01

- [ ] **T2.9 — Close two**
  - Release: R1 · Gate: phase-close
  - Verifies: [no-test: nothing]

| Test ID | Layer | File path · test | What it asserts |
|---|---|---|---|
| P2-V01 | unit | `x` | x |

## 7. Risks
"""


ROWS = (
    "| P1-V01 | unit | `a` | a |",
    "| P1-V02 | unit | `b` | b |",
    "| P1-V03 [manual] | CI | `c` | c |",
)


def write(tmp_path, name: str, text: str):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def run(tmp_path, spec: str, names: str, *extra: str) -> int:
    return tr.main(
        [
            "--spec", str(write(tmp_path, "SPEC.md", spec)),
            "--names", str(write(tmp_path, "names.txt", names)),
            "--workflows", str(tmp_path / "none"),
            *extra,
        ]
    )  # fmt: skip


def test_p1_v10_missing_id_fails(tmp_path, capsys):
    spec = spec_with(*ROWS)
    names = "tests/test_a.py::test_p1_v01_does_a\n"
    assert run(tmp_path, spec, names, "--release", "R1", "--through-phase", "1") == 1
    out = capsys.readouterr().out
    assert "P1-V02" in out
    assert "P1-V01" not in out.split("no test found for:")[1]

    names += "tests/test_b.py::test_p1_v02_does_b\n"
    assert run(tmp_path, spec, names, "--release", "R1", "--through-phase", "1") == 0
    assert "manual (listed, not required): P1-V03" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("names", "found"),
    [
        ("test_p1_v01_x", True),
        ("[desktop] › p1.spec.ts:3:1 › p1_v01 title", True),
        ("test_p1_v010_x", False),
        ("test_xp1_v01", False),
        ("TEST_P1_V01_UPPER", True),
    ],
)
def test_p1_v10_name_matching_is_exact(names, found):
    assert (tr.id_pattern("P1-V01").search(names.lower()) is not None) is found


def test_p1_v21_release_aware(tmp_path, capsys):
    rows = (*ROWS, "| P1-V04 [R2] | unit | `d` | d |", "| P1-V05 | unit | `e` | e |")
    spec = spec_with(*rows)
    names = "test_p1_v01_a\ntest_p1_v02_b\n"

    # An R1 ID with no test fails and is named; the [R2] ID without a test is not.
    assert run(tmp_path, spec, names, "--release", "R1", "--through-phase", "1") == 1
    out = capsys.readouterr().out
    assert "no test found for: P1-V05" in out
    assert "P1-V04" not in out.split("no test found for:")[1]

    names += "test_p1_v05_e\n"
    assert run(tmp_path, spec, names, "--release", "R1", "--through-phase", "1") == 0
    assert "1 deferred" in capsys.readouterr().out

    # With R2 in progress, the [R2] ID is required.
    assert run(tmp_path, spec, names, "--release", "R2", "--through-phase", "1") == 1
    assert "no test found for: P1-V04" in capsys.readouterr().out


def test_p1_v21_reads_only_the_verify_tables_of_section_6():
    ids = [row.id for row in specmd.verify_rows(spec_with(*ROWS))]
    assert ids == ["P1-V01", "P1-V02", "P1-V03", "P2-V01"]  # not REQ-900's P2-V01 [R2]


def test_p1_v21_current_phase_follows_the_phase_close_tasks():
    assert tr.current_phase(spec_with(*ROWS)) == 1
    assert tr.current_phase(spec_with(*ROWS, phase_close_done=True)) == 2


def test_p1_v21_through_phase_limits_the_ids(tmp_path):
    spec = spec_with(*ROWS)
    names = "test_p1_v01_a\ntest_p1_v02_b\n"
    assert (
        run(tmp_path, spec, names, "--release", "R1", "--through-phase", "current") == 0
    )
    assert run(tmp_path, spec, names, "--release", "R1") == 1  # P2-V01 has no test


def test_p1_v21_workflow_job_names_count(tmp_path):
    workflows = tmp_path / "wf"
    workflows.mkdir()
    (workflows / "ci.yml").write_text(
        "jobs:\n  p1_v02_job:\n    runs-on: x\n", encoding="utf-8"
    )
    code = tr.main(
        [
            "--spec", str(write(tmp_path, "SPEC.md", spec_with(*ROWS))),
            "--names", str(write(tmp_path, "names.txt", "test_p1_v01_a\n")),
            "--workflows", str(workflows),
            "--release", "R1",
            "--through-phase", "1",
        ]
    )  # fmt: skip
    assert code == 0


def test_appendix_matches_the_spec():
    """Appendix A of SPEC.md is what the script generates from §3 and §6."""
    spec = specmd.SPEC.read_text(encoding="utf-8")
    current = specmd.section(spec, "## Appendix A", "## Appendix B")
    current = current[current.index("| REQ |") :].strip()
    assert tr.appendix(spec) == current
