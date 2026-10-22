#!/usr/bin/env python3
"""Traceability check (SPEC.md §4.6, REQ-070).

Reads the first column of the Verify tables in SPEC.md §6 and fails (exit 1) when an in-scope ID
has no collected test whose name contains the ID in lowercase with underscores
(`P4-V01` -> `p4_v01`).

  [manual]   listed, never required
  [R2]       outside the release in progress (`--release R1`)

`--through-phase N|current|all` limits the check to the Verify IDs of phases 1..N. `current` is the
first phase whose `Gate: phase-close` task is not yet done, so the check grows as phases close.
`--appendix` prints Appendix A from §3 and §6 instead of checking.

Test names come from the files given to `--names` (one per collector, written by `make`
inside the container that owns each tool); without it the script runs the collectors itself.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

import specmd

COLLECTORS = (
    (["pytest", "--collect-only", "-q"], "api"),
    # The tests of scripts/ own P1-V06 and P1-V10, P1-V21 and P1-V22.
    (
        [
            "pytest",
            "--collect-only",
            "-q",
            "-c",
            "pytest.ini",
            "-p",
            "no:django",
            "tests",
        ],
        "scripts",
    ),
    (["npx", "vitest", "list"], "web"),
    (["npx", "playwright", "test", "--list"], "web"),
)


def release_rank(tag: str) -> int:
    return int(tag.lstrip("R"))


def current_phase(spec: str) -> int:
    """The first phase whose phase-close task is open; the last phase when all are closed."""
    closing = [t for t in specmd.tasks(spec) if t.phase_close]
    open_phases = [t.phase for t in closing if not t.done]
    return min(open_phases) if open_phases else max(t.phase for t in closing)


def id_pattern(verify_id: str) -> re.Pattern[str]:
    """`P4-V01` matches `test_p4_v01_x` and `p4_v01 title`, but not `p4_v010`."""
    token = verify_id.lower().replace("-", "_")
    return re.compile(rf"(?<![a-z0-9]){token}(?![0-9])")


def check_traceability(
    spec: str, names: str, release: str, through_phase: int | None = None
) -> dict[str, list[str]]:
    """Sorts every Verify ID of the spec into required, found, missing, manual and deferred."""
    corpus = names.lower()
    result: dict[str, list[str]] = {
        "required": [],
        "found": [],
        "missing": [],
        "manual": [],
        "deferred": [],
    }
    for row in specmd.verify_rows(spec):
        if through_phase is not None and row.phase > through_phase:
            continue
        if "manual" in row.tags:
            result["manual"].append(row.id)
        elif any(
            tag.startswith("R") and release_rank(tag) > release_rank(release)
            for tag in row.tags
        ):
            result["deferred"].append(row.id)
        else:
            result["required"].append(row.id)
            found = id_pattern(row.id).search(corpus)
            result["found" if found else "missing"].append(row.id)
    return result


def appendix(spec: str) -> str:
    """Appendix A: each §3 requirement, the tasks that own its acceptance IDs, and the IDs."""
    tags = {row.id: row.tags for row in specmd.verify_rows(spec)}
    owners: dict[str, list[str]] = {}
    for task in specmd.tasks(spec):
        for verify_id in task.verifies:
            owners.setdefault(verify_id, []).append(task.id)
    lines = ["| REQ | Release | Tasks | Verify IDs |", "|---|---|---|---|"]
    acceptance: set[str] = set()
    for header, body in specmd.tables(specmd.section(spec, "## 3.", "## 4.")):
        if header[:1] != ["REQ"]:
            continue
        for cells in body:
            ids = specmd.VERIFY_ID.findall(cells[3])
            acceptance.update(ids)
            ordered = [i for i in ids if "R2" not in tags.get(i, [])] + [
                i for i in ids if "R2" in tags.get(i, [])
            ]
            task_ids: list[str] = []
            for verify_id in ordered:
                for owner in owners.get(verify_id, []):
                    if owner not in task_ids:
                        task_ids.append(owner)
            labels = [
                i + "".join(f" [{t}]" for t in tags.get(i, []) if t == "R2")
                for i in ordered
            ]
            lines.append(
                f"| {cells[0]} | {cells[4]} | {', '.join(task_ids)} | {' · '.join(labels)} |"
            )
    total = len(tags)
    lines += [
        "",
        f"{total} Verify IDs in §6; {len(acceptance)} are acceptance criteria of a §3 requirement. "
        "The others are feature-level checks of their phase (OA-02).",
    ]
    return "\n".join(lines)


def collect_names(repo: Path) -> str:
    """Test names from pytest, vitest and playwright, plus the CI job names."""
    parts = []
    for command, directory in COLLECTORS:
        done = subprocess.run(
            command, cwd=repo / directory, capture_output=True, text=True, check=False
        )
        if done.returncode not in (0, 5):  # pytest exits 5 when it collects nothing
            sys.exit(
                f"{' '.join(command)} failed ({done.returncode}):\n{done.stdout}{done.stderr}"
            )
        parts.append(done.stdout)
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--release", required=True, help="the release in progress, for example R1"
    )
    parser.add_argument("--spec", type=Path, default=specmd.SPEC)
    parser.add_argument(
        "--names", type=Path, nargs="*", help="files of collected test names"
    )
    parser.add_argument(
        "--workflows", type=Path, default=specmd.REPO / ".github" / "workflows"
    )
    parser.add_argument("--through-phase", help="a phase number, or `current`")
    parser.add_argument(
        "--appendix", action="store_true", help="print Appendix A and exit"
    )
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    spec = args.spec.read_text(encoding="utf-8")
    if args.appendix:
        print(appendix(spec))
        return 0

    names = (
        "\n".join(p.read_text(encoding="utf-8") for p in args.names)
        if args.names
        else collect_names(specmd.REPO)
    )
    if args.workflows.is_dir():
        names += "\n" + "\n".join(
            p.read_text(encoding="utf-8") for p in sorted(args.workflows.glob("*.y*ml"))
        )

    through = None
    if args.through_phase in ("current", "all", None):
        through = current_phase(spec) if args.through_phase == "current" else None
    else:
        through = int(args.through_phase)
    result = check_traceability(spec, names, args.release, through)

    scope = f" through phase {through}" if through else ""
    summary = (
        f"traceability {args.release}{scope}: {len(result['found'])}/{len(result['required'])} IDs "
        f"have a test; {len(result['manual'])} manual, {len(result['deferred'])} deferred"
    )
    if result["manual"]:
        print("manual (listed, not required): " + ", ".join(result["manual"]))
    if result["missing"]:
        print("no test found for: " + ", ".join(result["missing"]))
        print(summary)
        return 1
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
