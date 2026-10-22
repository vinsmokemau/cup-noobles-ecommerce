"""P1-V22: the register in §2.4 matches the code and the tests (SPEC.md §4.6)."""

import check_register as cr
import specmd

SPEC = """# Fixture

### 2.2 Conflicts and their resolutions

| ID | Conflict | Resolution | Status |
|---|---|---|---|
| C-01 | A conflict | Settled | Resolved (OA-1) |

### 2.3 Assumptions

### 2.4 Open-items register

| ID | Question | Needed by | Release | Status |
|---|---|---|---|---|
| D1 | An open decision | Phase 2 | R1 | Open |
| D2 | A made decision | Phase 2 | R1 | Decided (OA-2) |
| S1 | Needs a pipe \\| in the text | Phase 1 | R1 | Resolved (ADR-0001) |

| ID | Owning phase | Exposed by | Gap | Proposed | Release | Status |
|---|---|---|---|---|---|---|
| G1 | 1 | P1-V01 | A gap | A fix | R1 | Open |
| G2 | 1 | P1-V02 | A gap | A fix | R1 | Resolved (ADR-0002) |
| G3 | 1 | P1-V03 | A gap | A fix | R1 | Resolved (DS:ADR-0099) |

| ID | Request | Needed by | Release | Status |
|---|---|---|---|---|
| DSR-01 | A request | Phase 12 | R1 | Open |

### 2.5 Dev defaults
"""

XFAIL = 'import pytest\n\n@pytest.mark.xfail(strict=True, reason="{}")\ndef test_a():\n    pass\n'


def tree(
    tmp_path, files: dict[str, str], adrs: tuple[str, ...] = ("0001", "0002")
) -> list[str]:
    for number in adrs:
        adr = tmp_path / "docs" / "decisions" / f"{number}-x.md"
        adr.parent.mkdir(parents=True, exist_ok=True)
        adr.write_text("# ADR\n", encoding="utf-8")
    for name, source in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    return cr.check_register(SPEC, tmp_path)


def test_p1_v22_register_consistency(tmp_path):
    # Every kind of citation resolves: test name, xfail reason, comment, TypeScript.
    clean = {
        "api/tests/test_ok.py": (
            "import pytest\n\n"
            "# See G1 and DSR-01 and C-01.\n"
            '@pytest.mark.xfail(strict=True, reason="G1")\n'
            "def test_p9_v01_thing_g1():\n    pass\n"
        ),
        "web/e2e/ok.spec.ts": (
            "// D1 stays open\n"
            "test('p1_v01 something g1', async () => {})\n"
            "test.fixme(true, 'DSR-01')\n"
        ),
    }
    assert tree(tmp_path, clean) == []

    def problems(
        name: str, source: str, adrs: tuple[str, ...] = ("0001", "0002")
    ) -> list[str]:
        sub = tmp_path / name.replace("/", "_").replace(".", "_")
        sub.mkdir()
        return tree(sub, {name: source}, adrs)

    # An ID absent from the register: in a test name, an xfail reason, a comment, a TS title.
    assert "G99" in "".join(
        problems("api/tests/t1.py", "def test_x_g99_y():\n    pass\n")
    )
    assert "S9" in "".join(problems("api/tests/t2.py", XFAIL.format("S9")))
    assert "DSR-77" in "".join(problems("api/app.py", "x = 1  # waits for DSR-77\n"))
    assert "C-50" in "".join(problems("web/app/a.ts", "// C-50\n"))
    assert "D40" in "".join(
        problems("web/e2e/b.spec.ts", "test('p1_v01 d40', () => {})\n")
    )

    # A Decided or Resolved item with an xfail.
    decided = problems("api/tests/t3.py", XFAIL.format("D2"))
    assert any("D2" in line and "still has an xfail" in line for line in decided)
    resolved = problems("api/tests/t4.py", XFAIL.format("G2"))
    assert any("G2" in line and "still has an xfail" in line for line in resolved)

    # A Resolved item citing an ADR file that doesn't exist; DS:ADR-NNNN is not ours.
    missing = problems("api/ok.py", "x = 1\n", adrs=("0001",))
    assert missing == ["G2 cites ADR-0002, but docs/decisions/ has no such file"]


def test_p1_v22_strings_in_test_fixtures_are_not_citations(tmp_path):
    """A string that merely contains `xfail(reason="G99")` is not an xfail."""
    source = "FIXTURE = '@pytest.mark.xfail(reason=\"G99\")  # G98'\n"
    assert tree(tmp_path, {"scripts/tests/test_fixture.py": source}) == []


def test_p1_v22_pipes_escaped_in_cells_stay_in_the_cell():
    items = cr.register(SPEC)
    assert items["S1"] == "Resolved (ADR-0001)"
    assert set(items) == {"C-01", "D1", "D2", "S1", "G1", "G2", "G3", "DSR-01"}


def test_p1_v22_the_real_tree_passes():
    spec = specmd.SPEC.read_text(encoding="utf-8")
    assert cr.check_register(spec, specmd.REPO) == []
