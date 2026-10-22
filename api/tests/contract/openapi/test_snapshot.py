"""P1-V07: a change to the API contract fails the build until the snapshot is updated."""

from tests.contract.openapi.snapshot import (
    SNAPSHOT_PATH,
    generate_schema_text,
    schema_diff,
)

SCHEMA = """\
openapi: 3.1.0
paths:
  /api/products/:
    get:
      responses:
        '200':
          content:
            application/json:
              schema:
                type: object
                properties:
                  name:
                    type: string
"""


def test_p1_v07_snapshot_detects_drift():
    renamed = SCHEMA.replace("name:", "title:")
    diff = schema_diff(SCHEMA, renamed)
    assert any(line.startswith("-") and "name:" in line for line in diff)
    assert any(line.startswith("+") and "title:" in line for line in diff)
    assert schema_diff(SCHEMA, SCHEMA) == []


def test_snapshot_matches_live_schema():
    diff = schema_diff(
        SNAPSHOT_PATH.read_text(encoding="utf-8"), generate_schema_text()
    )
    assert not diff, (
        "openapi.snapshot.yml is out of date; run `make schema-update`:\n"
        + "\n".join(diff)
    )
