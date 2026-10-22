"""Shared `ast` scan behind the state and stock boundary tests (SPEC.md §4.6)."""

import ast
from collections.abc import Collection
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[2]


def _assigned_attributes(target: ast.expr) -> list[ast.Attribute]:
    if isinstance(target, ast.Attribute):
        return [target]
    if isinstance(target, ast.Tuple | ast.List):
        return [a for element in target.elts for a in _assigned_attributes(element)]
    if isinstance(target, ast.Starred):
        return _assigned_attributes(target.value)
    return []


def _is_constant_str(node: ast.expr, fields: Collection[str]) -> bool:
    return isinstance(node, ast.Constant) and node.value in fields


def field_write_violations(
    path: str, source: str, fields: Collection[str], allowed: Collection[str]
) -> list[str]:
    """Writes to any of `fields` in `source`, unless `path` is in `allowed`.

    Catches `obj.f = …`, `obj.f += …`, annotated and tuple assignments,
    `setattr(obj, "f", …)` and `.update(f=…)`. `path` is relative to `api/`,
    with forward slashes.
    """
    if path in allowed:
        return []
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AugAssign | ast.AnnAssign):
            targets = [node.target]
        else:
            targets = []
        for target in targets:
            found += [
                (a.lineno, f"assigns .{a.attr}")
                for a in _assigned_attributes(target)
                if a.attr in fields
            ]
        if not isinstance(node, ast.Call):
            continue
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "setattr"
            and len(node.args) >= 2
            and _is_constant_str(node.args[1], fields)
        ):
            found.append(
                (node.lineno, f"setattr(…, {ast.literal_eval(node.args[1])!r}, …)")
            )
        if isinstance(node.func, ast.Attribute) and node.func.attr == "update":
            found += [
                (node.lineno, f".update({kw.arg}=…)")
                for kw in node.keywords
                if kw.arg in fields
            ]
    return [f"{path}:{line}: {what}" for line, what in sorted(found)]


def scan_apps(fields: Collection[str], allowed: Collection[str]) -> list[str]:
    violations = []
    for file in sorted((API_DIR / "apps").rglob("*.py")):
        path = file.relative_to(API_DIR).as_posix()
        violations += field_write_violations(
            path, file.read_text(encoding="utf-8"), fields, allowed
        )
    return violations
