"""Reading SPEC.md: sections, pipe tables and the task list (SPEC.md §0.4, §6)."""

import re
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SPEC = REPO / "SPEC.md"

VERIFY_ID = re.compile(r"P\d+-V\d+")


def section(text: str, start: str, end: str) -> str:
    """The text between the heading line starting with `start` and the one starting with `end`."""
    begin = re.search(rf"^{re.escape(start)}", text, re.MULTILINE)
    if begin is None:
        raise ValueError(f"SPEC.md has no heading starting with {start!r}")
    stop = re.compile(rf"^{re.escape(end)}", re.MULTILINE).search(text, begin.end())
    return text[begin.start() : stop.start() if stop else len(text)]


def split_row(line: str) -> list[str]:
    """The cells of a table row; `\\|` stays inside its cell."""
    cells = re.split(r"(?<!\\)\|", line.strip())
    return [cell.strip() for cell in cells[1:-1]]


def tables(text: str) -> list[tuple[list[str], list[list[str]]]]:
    """Every pipe table as (header cells, body rows)."""
    found = []
    lines = text.splitlines()
    i = 0
    while i < len(lines) - 1:
        if lines[i].startswith("|") and re.match(r"^\|[\s:|-]+\|\s*$", lines[i + 1]):
            header = split_row(lines[i])
            rows = []
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            found.append((header, rows))
        else:
            i += 1
    return found


@dataclass
class VerifyRow:
    id: str
    tags: list[str]
    phase: int


@dataclass
class Task:
    id: str
    done: bool
    phase: int
    phase_close: bool = False
    verifies: list[str] = field(default_factory=list)
    reqs: list[str] = field(default_factory=list)


def verify_rows(spec: str) -> list[VerifyRow]:
    """The first column of every `Test ID` table in §6: an ID with its `[manual]` or `[R2]` tags."""
    rows = []
    for header, body in tables(section(spec, "## 6.", "## 7.")):
        if header[:1] != ["Test ID"]:
            continue
        for cells in body:
            match = re.match(rf"({VERIFY_ID.pattern})\s*(.*)$", cells[0])
            if match:
                tags = re.findall(r"\[([^\]]+)\]", match.group(2))
                rows.append(
                    VerifyRow(
                        match.group(1),
                        tags,
                        int(match.group(1)[1 : match.group(1).index("-")]),
                    )
                )
    return rows


def tasks(spec: str) -> list[Task]:
    """The tasks of §6 with their phase, gate, Verify IDs and REQs."""
    found: list[Task] = []
    phase = 0
    for line in section(spec, "## 6.", "## 7.").splitlines():
        heading = re.match(r"### Phase (\d+) ", line)
        if heading:
            phase = int(heading.group(1))
        head = re.match(r"- \[( |x)\] \*\*(T\d+\.\d+[a-z]?) — ", line)
        if head:
            found.append(Task(head.group(2), head.group(1) == "x", phase))
        elif found and (
            field_line := re.match(r"\s+- (Release|REQs|Verifies): ?(.*)$", line)
        ):
            name, value = field_line.groups()
            task = found[-1]
            if name == "Release":
                task.phase_close = "Gate: phase-close" in value
            elif name == "Verifies":
                task.verifies = (
                    VERIFY_ID.findall(value) if not value.startswith("[no-test") else []
                )
            else:
                task.reqs = re.findall(r"REQ-\d+", value)
    return found
