"""P1-V07: a change to the API contract fails the build until the snapshot is updated."""

import gc

import pytest
from rest_framework import serializers

from apps.catalog.serializers import ProductCardSerializer
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


def _drop_cached_fields() -> None:
    """The view decorators hold serializer instances made at import; forget their fields."""
    for obj in gc.get_objects():
        if issubclass(type(obj), ProductCardSerializer):
            obj.__dict__.pop("fields", None)


@pytest.mark.django_db
def test_p5_v04_serializer_rename_breaks_snapshot(monkeypatch):
    declared = {
        **ProductCardSerializer._declared_fields,
        "title": serializers.CharField(source="name"),
    }
    fields = [
        "title" if name == "name" else name
        for name in ProductCardSerializer.Meta.fields
    ]
    monkeypatch.setattr(ProductCardSerializer, "_declared_fields", declared)
    monkeypatch.setattr(ProductCardSerializer.Meta, "fields", fields)
    _drop_cached_fields()
    try:
        diff = schema_diff(
            SNAPSHOT_PATH.read_text(encoding="utf-8"), generate_schema_text()
        )
    finally:
        monkeypatch.undo()
        _drop_cached_fields()
    assert any(line.startswith("+") and "title:" in line for line in diff)
    assert any(line.startswith("-") and "name:" in line for line in diff)
