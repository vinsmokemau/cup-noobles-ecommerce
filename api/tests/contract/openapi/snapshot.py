"""Comparator for the committed OpenAPI snapshot (SPEC.md §4.6, REQ-054)."""

import difflib
from io import StringIO
from pathlib import Path

from django.core.management import call_command

SNAPSHOT_PATH = Path(__file__).resolve().parents[3] / "openapi.snapshot.yml"


def generate_schema_text() -> str:
    """The live schema, from the same command `make schema-update` runs."""
    out = StringIO()
    call_command("spectacular", "--validate", "--fail-on-warn", stdout=out)
    return out.getvalue()


def schema_diff(expected: str, actual: str) -> list[str]:
    """Unified diff lines from the snapshot to the live schema; empty when equal."""
    return list(
        difflib.unified_diff(
            expected.splitlines(),
            actual.splitlines(),
            fromfile="openapi.snapshot.yml",
            tofile="live schema",
            lineterm="",
        )
    )
