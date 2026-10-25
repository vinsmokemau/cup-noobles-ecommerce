"""P5-V07, P5-V08: the public availability status (T5.3).

The catalog endpoints arrive in T5.1; until then the "response" is the rendered JSON of the
variant availability serializer they will embed.
"""

import json

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.renderers import JSONRenderer

from apps.catalog.availability import with_available_units
from apps.catalog.models import Variant
from apps.catalog.serializers import VariantAvailabilitySerializer
from apps.inventory.models import Location
from tests.factories.inventory import LocationFactory, holding_order, stocked_variant

pytestmark = pytest.mark.django_db


def payload(variants) -> dict:
    """The JSON a client reads for `variants`, as a mapping from public id."""
    data = VariantAvailabilitySerializer(variants, many=True).data
    return {row["public_id"]: json.loads(JSONRenderer().render(row)) for row in data}


# G13: the boundary at 5 follows 5.3 (1 <= available <= 5); D10 says "under 5".
@pytest.mark.parametrize(
    ("available", "status"),
    [
        (0, "out_of_stock"),
        (1, "low_stock"),
        (5, "low_stock"),
        (6, "in_stock"),
    ],
)
def test_p5_v07_status_boundaries(available, status):
    variant = stocked_variant(on_hand=available)

    row = payload([variant])[str(variant.public_id)]

    assert row["availability"] == {"status": status}


def test_p5_v07_status_counts_reservations_and_safety_stock():
    held = stocked_variant(on_hand=8)
    holding_order(held, 3)  # available 5 -> low_stock
    safe = stocked_variant(on_hand=8, safety_stock=3)  # available 5 -> low_stock
    drained = stocked_variant(on_hand=4, safety_stock=4)  # available 0 -> out_of_stock
    unstocked = Variant.objects.get(pk=stocked_variant(on_hand=0).pk)

    rows = payload([held, safe, drained, unstocked])

    assert [r["availability"]["status"] for r in rows.values()] == [
        "low_stock",
        "low_stock",
        "out_of_stock",
        "out_of_stock",
    ]


def test_p5_v07_sums_fulfillment_locations_only():
    variant = stocked_variant(on_hand=4)
    second = LocationFactory(code="bodega", name="Bodega de prueba")
    from apps.inventory import services
    from tests.factories.inventory import StockItemFactory

    StockItemFactory(variant=variant, location=second)
    services.receive_stock(variant, second, 3)
    closed = LocationFactory(code="cerrada", name="Cerrada")
    Location.objects.filter(pk=closed.pk).update(is_active=False)
    StockItemFactory(variant=variant, location=closed)
    services.receive_stock(variant, closed, 50)

    row = payload([variant])[str(variant.public_id)]

    assert row["availability"] == {"status": "in_stock"}  # 4 + 3, not 57 and not 4


def test_p5_v07_annotation_needs_no_query_per_variant():
    variants = [stocked_variant(on_hand=n) for n in (0, 2, 9)]
    queryset = with_available_units(
        Variant.objects.filter(pk__in=[v.pk for v in variants])
    )

    with CaptureQueriesContext(connection) as queries:
        rows = VariantAvailabilitySerializer(queryset, many=True).data

    assert len(queries) == 1
    assert sorted(r["availability"]["status"] for r in rows) == [
        "in_stock",
        "low_stock",
        "out_of_stock",
    ]


def test_p5_v08_no_raw_counts_exposed():
    variant = stocked_variant(on_hand=7, safety_stock=1)
    holding_order(variant, 2)

    body = json.dumps(payload([variant]))

    for forbidden in ("on_hand", "reserved", "safety_stock", "available_units"):
        assert forbidden not in body
    row = json.loads(body)[str(variant.public_id)]
    assert set(row) == {"public_id", "availability"}
    assert set(row["availability"]) == {"status"}
    assert isinstance(row["availability"]["status"], str)
