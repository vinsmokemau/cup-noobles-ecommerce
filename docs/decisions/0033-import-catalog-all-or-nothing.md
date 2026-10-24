# ADR-0033: The catalog importer is all or nothing per file

## Status

accepted (2026-10-24)

## Context

`manage.py import_catalog` (T3.6) reads a CSV of many rows. SPEC.md did not say what happens to the valid rows when some rows are invalid (G12, P3-V09).

## Decision

1. If any row of the file is invalid, nothing is written. The importer reports every invalid row, each with its row number and column.
2. `--dry-run` follows the same rules and writes nothing.
3. Image files are stored only after the database commit, so an aborted run leaves no files in media storage.

## Consequences

- A catalog file is either imported whole or not at all, so a half-imported catalog cannot happen.
- The owner fixes all reported rows and runs the file again; the import is idempotent on SKU, so a re-run is safe.
- Switching to "import the valid rows" later would change `import_catalog` in `apps/catalog/importer.py` and P3-V09.

## Source

G12; OA-31 (2026-10-24); T3.6.
