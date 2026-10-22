#!/usr/bin/env python3
"""Coverage gates and ratchet (SPEC.md §4.6, CR-44).

Three scopes, each a percentage to two decimals:

  critical     branch coverage of apps/inventory, apps/orders and apps/payments
  backend      branch coverage of apps/
  composables  the lowest of lines, branches, functions and statements in web/app/composables

Fails (exit 1) when a scope is below its gate, below `coverage-baseline.json`, or when the
baseline file was lowered against HEAD. `--update` rewrites the baseline after coverage rose.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

GATES = {"critical": 95.0, "backend": 85.0, "composables": 80.0}
CRITICAL_PREFIXES = ("apps/inventory/", "apps/orders/", "apps/payments/")
COMPOSABLE_METRICS = ("lines", "branches", "functions", "statements")


def percent(covered: int, total: int) -> float:
    """A scope with nothing to measure is fully covered."""
    return 100.0 if total == 0 else round(100 * covered / total, 2)


def backend_scopes(report: dict) -> dict[str, float]:
    """coverage.py's branch measure: (lines + branches covered) / (statements + branches)."""
    totals = {"critical": [0, 0], "backend": [0, 0]}
    for path, data in report["files"].items():
        summary = data["summary"]
        covered = summary["covered_lines"] + summary.get("covered_branches", 0)
        total = summary["num_statements"] + summary.get("num_branches", 0)
        scopes = ["backend"]
        if path.startswith(CRITICAL_PREFIXES):
            scopes.append("critical")
        for scope in scopes:
            totals[scope][0] += covered
            totals[scope][1] += total
    return {scope: percent(*pair) for scope, pair in totals.items()}


def composables_scope(summary: dict) -> float:
    """vitest's json-summary reports "Unknown" when no composable exists yet."""
    values = []
    for metric in COMPOSABLE_METRICS:
        pct = summary["total"][metric]["pct"]
        values.append(100.0 if pct == "Unknown" else float(pct))
    return round(min(values), 2)


def measure(backend_path: Path, composables_path: Path) -> dict[str, float]:
    scopes = backend_scopes(json.loads(backend_path.read_text(encoding="utf-8")))
    scopes["composables"] = composables_scope(
        json.loads(composables_path.read_text(encoding="utf-8"))
    )
    return scopes


def read_baseline(path: Path | None) -> dict[str, float] | None:
    if path is None or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def baseline_at_head(path: Path) -> dict[str, float] | None:
    """The baseline as committed at HEAD; None when git or the file is not there."""
    try:
        shown = subprocess.run(
            ["git", "show", f"HEAD:{path.as_posix()}"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return json.loads(shown.stdout)


def gate_failures(current: dict[str, float]) -> list[str]:
    return [
        f"{scope}: {current[scope]:.2f}% is below its gate of {gate:.0f}%"
        for scope, gate in GATES.items()
        if current[scope] < gate
    ]


def ratchet_failures(
    current: dict[str, float],
    baseline: dict[str, float] | None,
    head: dict[str, float] | None,
) -> list[str]:
    if baseline is None:
        return ["coverage-baseline.json is missing; run `make coverage-ratchet`"]
    failures = []
    for scope in GATES:
        if current[scope] < baseline[scope]:
            failures.append(
                f"{scope}: {current[scope]:.2f}% is below the baseline of {baseline[scope]:.2f}%"
            )
        if head is not None and baseline[scope] < head[scope]:
            failures.append(
                f"{scope}: the baseline was lowered from {head[scope]:.2f}% (HEAD) to {baseline[scope]:.2f}%"
            )
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--backend", type=Path, default=Path("api/coverage.json"))
    parser.add_argument(
        "--composables", type=Path, default=Path("web/coverage/coverage-summary.json")
    )
    parser.add_argument("--baseline", type=Path, default=Path("coverage-baseline.json"))
    parser.add_argument(
        "--head-baseline",
        type=Path,
        help="the baseline as committed at HEAD (default: asked from git)",
    )
    parser.add_argument(
        "--only",
        choices=["gates", "ratchet", "report"],
        help="run one check (default: gates and ratchet)",
    )
    parser.add_argument(
        "--update", action="store_true", help="rewrite the baseline after a rise"
    )
    args = parser.parse_args(argv)

    current = measure(args.backend, args.composables)
    print(" · ".join(f"{scope} {value:.2f}%" for scope, value in current.items()))
    if args.only == "report":
        return 0

    baseline = read_baseline(args.baseline)
    if args.update:
        if baseline is not None:
            lower = ratchet_failures(current, baseline, None)
            if lower:
                print("\n".join(lower))
                return 1
        args.baseline.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.baseline}")
        return 0

    failures = []
    if args.only in (None, "gates"):
        failures += gate_failures(current)
    if args.only in (None, "ratchet"):
        head = (
            read_baseline(args.head_baseline)
            if args.head_baseline
            else baseline_at_head(args.baseline)
        )
        failures += ratchet_failures(current, baseline, head)
    if failures:
        print("\n".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
