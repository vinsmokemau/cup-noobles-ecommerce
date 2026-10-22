#!/usr/bin/env python3
"""Register check (SPEC.md §4.6, P1-V22).

Fails (exit 1) when
  - a test name, an `xfail` reason or a code comment cites an S, D, G, C or DSR ID that SPEC.md
    §2.2 or §2.4 doesn't list;
  - an item marked Resolved or Decided still has an `xfail`;
  - a Resolved item cites an ADR (`ADR-NNNN`, not `DS:ADR-NNNN`) with no file in docs/decisions/.

Scans Python under api/ and scripts/, and TypeScript and Vue under web/.
"""

import argparse
import ast
import io
import os
import re
import sys
import tokenize
from pathlib import Path

import specmd

ITEM = r"(?:[SDG]\d+|DSR-\d+|C-\d+)"
ITEM_IN_TEXT = re.compile(rf"(?<![\w:-])({ITEM})(?![\w-])")
ITEM_IN_NAME = re.compile(r"(?<![a-z0-9])(?:([sdg]\d+)|(dsr|c)_(\d+))(?![a-z0-9])")
OWN_ID = re.compile(r"^(?:[SDG]\d+|DSR-\d+|C-\d+)$")
OWN_ADR = re.compile(r"(?<!DS:)ADR-(\d{4})")
SKIPPED_DIRS = {
    "node_modules", ".venv", ".nuxt", ".output", ".git", "__pycache__", "coverage", "var",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist",
}  # fmt: skip
TS_TITLE = re.compile(
    r"""\b(?:test|it|describe)(?:\.\w+)*\(\s*(['"`])((?:\\.|(?!\1).)*)\1"""
)
TS_COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)
TS_FAIL = re.compile(
    r"""\btest\.(?:fail|fixme|skip)\([^)]*?(['"`])((?:\\.|(?!\1).)*)\1"""
)


def register(spec: str) -> dict[str, str]:
    """Every item of §2.2 (conflicts) and §2.4 (the register) with its status cell."""
    items: dict[str, str] = {}
    for start, end in (("### 2.2", "### 2.3"), ("### 2.4", "### 2.5")):
        for _header, rows in specmd.tables(specmd.section(spec, start, end)):
            for cells in rows:
                if OWN_ID.match(cells[0]):
                    items[cells[0]] = cells[-1]
    return items


def is_closed(status: str) -> bool:
    return status.startswith(("Resolved", "Decided"))


class Citation:
    def __init__(self, item: str, where: str, kind: str):
        self.item, self.where, self.kind = item, where, kind


def ids_in_name(name: str) -> list[str]:
    found = []
    for match in ITEM_IN_NAME.finditer(name.lower()):
        if match.group(1):
            found.append(match.group(1).upper())
        else:
            found.append(f"{match.group(2).upper()}-{match.group(3).zfill(2)}")
    return found


def ids_in_text(text: str) -> list[str]:
    return ITEM_IN_TEXT.findall(text)


def is_xfail_call(node: ast.Call) -> bool:
    func = node.func
    return (isinstance(func, ast.Attribute) and func.attr == "xfail") or (
        isinstance(func, ast.Name) and func.id == "xfail"
    )


def python_citations(path: Path, source: str) -> list[Citation]:
    where = str(path)
    found = []
    try:
        tree = ast.parse(source)
        comments = [
            (tok.start[0], tok.string)
            for tok in tokenize.generate_tokens(io.StringIO(source).readline)
            if tok.type == tokenize.COMMENT
        ]
    except (SyntaxError, tokenize.TokenError):
        return [Citation("PARSE", f"{where}: cannot parse", "error")]
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef)
        ) and node.name.startswith("test"):
            found += [
                Citation(i, f"{where}:{node.lineno}", "test name")
                for i in ids_in_name(node.name)
            ]
        elif isinstance(node, ast.Call) and is_xfail_call(node):
            for keyword in node.keywords:
                if keyword.arg == "reason" and isinstance(keyword.value, ast.Constant):
                    found += [
                        Citation(i, f"{where}:{node.lineno}", "xfail")
                        for i in ids_in_text(str(keyword.value.value))
                    ]
    for line, text in comments:
        found += [Citation(i, f"{where}:{line}", "comment") for i in ids_in_text(text)]
    return found


def typescript_citations(path: Path, source: str) -> list[Citation]:
    where = str(path)

    def line_of(offset: int) -> int:
        return source.count("\n", 0, offset) + 1

    found = []
    for match in TS_TITLE.finditer(source):
        found += [
            Citation(i, f"{where}:{line_of(match.start())}", "test name")
            for i in ids_in_name(match.group(2).replace(" ", "_"))
        ]
    for match in TS_FAIL.finditer(source):
        found += [
            Citation(i, f"{where}:{line_of(match.start())}", "xfail")
            for i in ids_in_text(match.group(2))
        ]
    for match in TS_COMMENT.finditer(source):
        found += [
            Citation(i, f"{where}:{line_of(match.start())}", "comment")
            for i in ids_in_text(match.group(0))
        ]
    return found


def source_files(repo: Path) -> list[Path]:
    """The files to scan; skipped directories are pruned, never walked."""
    files = []
    for root, suffixes in (
        ("api", {".py"}),
        ("scripts", {".py"}),
        ("web", {".ts", ".vue", ".mjs", ".js"}),
    ):
        for directory, dirs, names in os.walk(repo / root):
            dirs[:] = sorted(d for d in dirs if d not in SKIPPED_DIRS)
            files += [
                Path(directory) / name
                for name in sorted(names)
                if Path(name).suffix in suffixes
            ]
    return files


def check_register(spec: str, repo: Path, files: list[Path] | None = None) -> list[str]:
    """Every problem found, one line each; an empty list means the register is consistent."""
    items = register(spec)
    problems = []
    xfails: dict[str, list[str]] = {}
    for path in source_files(repo) if files is None else files:
        source = path.read_text(encoding="utf-8")
        rel = path.relative_to(repo) if path.is_relative_to(repo) else path
        citations = (
            python_citations(rel, source)
            if path.suffix == ".py"
            else typescript_citations(rel, source)
        )
        for citation in citations:
            if citation.kind == "error":
                problems.append(citation.where)
            elif citation.item not in items:
                problems.append(
                    f"{citation.where}: {citation.kind} cites {citation.item}, which §2.2 and §2.4 don't list"
                )
            elif citation.kind == "xfail":
                xfails.setdefault(citation.item, []).append(citation.where)
    for item, places in sorted(xfails.items()):
        if is_closed(items[item]):
            problems.append(
                f"{item} is {items[item].split(';')[0]} but still has an xfail: {', '.join(places)}"
            )
    decisions = repo / "docs" / "decisions"
    for item, status in sorted(items.items()):
        if status.startswith("Resolved"):
            for number in OWN_ADR.findall(status):
                if not list(decisions.glob(f"{number}-*.md")):
                    problems.append(
                        f"{item} cites ADR-{number}, but docs/decisions/ has no such file"
                    )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--spec", type=Path, default=specmd.SPEC)
    parser.add_argument("--repo", type=Path, default=specmd.REPO)
    args = parser.parse_args(argv)

    spec = args.spec.read_text(encoding="utf-8")
    problems = check_register(spec, args.repo)
    if problems:
        print("\n".join(problems))
        print(f"register: {len(problems)} problem(s)")
        return 1
    print(f"register: {len(register(spec))} items, every citation resolves")
    return 0


if __name__ == "__main__":
    sys.exit(main())
