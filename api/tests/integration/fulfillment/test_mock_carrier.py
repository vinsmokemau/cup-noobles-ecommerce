"""The mock carrier (SPEC.md 10.9, P10-V03)."""

import json
import shutil
from pathlib import Path

import pytest
from django.conf import settings

from apps.shipping.carriers.base import ShipmentStatus
from apps.shipping.carriers.mock import MockCarrier
from tests.factories.orders import OrderFactory, ShipmentFactory

pytestmark = pytest.mark.django_db


def _store() -> Path:
    return Path(settings.MOCK_STORE_DIR) / "carrier"


def test_p10_v03_tracking_numbers_deterministic():
    carrier = MockCarrier()
    order = OrderFactory(number="CN-2026-000123")

    first = carrier.create_shipment(order)
    ShipmentFactory(
        order=order, carrier=first.carrier, tracking_number=first.tracking_number
    )
    second = carrier.create_shipment(order)

    assert first.tracking_number == "MOCK-CN-2026-000123-1"
    assert second.tracking_number == "MOCK-CN-2026-000123-2"

    order.delete()
    shutil.rmtree(_store())
    reborn = OrderFactory(number="CN-2026-000123")

    assert carrier.create_shipment(reborn).tracking_number == first.tracking_number


def test_a_number_typed_by_staff_is_used_as_given():
    ref = MockCarrier().create_shipment(OrderFactory(), tracking_number="GUIA-77")

    assert ref.tracking_number == "GUIA-77"
    assert ref.carrier == "mock"


def test_tracking_url_points_at_the_dev_page(settings):
    settings.SITE_URL = "http://localhost:8080"
    order = OrderFactory(number="CN-2026-000007")

    ref = MockCarrier().create_shipment(order)

    assert (
        ref.tracking_url
        == "http://localhost:8080/dev/carrier/track/MOCK-CN-2026-000007-1/"
    )


def test_a_new_shipment_starts_in_transit_with_one_event():
    carrier = MockCarrier()
    ref = carrier.create_shipment(OrderFactory())

    stored = json.loads((_store() / f"{ref.tracking_number}.json").read_text())

    assert carrier.get_status(ref.tracking_number) is ShipmentStatus.IN_TRANSIT
    assert stored["status"] == "in_transit"
    assert [event["status"] for event in stored["events"]] == ["in_transit"]


def test_get_status_returns_the_stored_status():
    carrier = MockCarrier()
    ref = carrier.create_shipment(OrderFactory())
    path = _store() / f"{ref.tracking_number}.json"
    stored = json.loads(path.read_text())
    stored["status"] = "delivered"
    path.write_text(json.dumps(stored))

    assert carrier.get_status(ref.tracking_number) is ShipmentStatus.DELIVERED


def test_an_unknown_tracking_number_is_unknown():
    assert MockCarrier().get_status("NOPE-1") is ShipmentStatus.UNKNOWN


def test_a_tracking_number_cannot_name_a_path_outside_the_store():
    carrier = MockCarrier()

    carrier.create_shipment(OrderFactory(), tracking_number="../../escape")

    assert not (Path(settings.MOCK_STORE_DIR) / "escape.json").exists()
    assert carrier.get_status("../../escape") is ShipmentStatus.IN_TRANSIT
    assert [p.name for p in _store().iterdir()] == ["..%2F..%2Fescape.json"]


def test_the_provider_switch_loads_the_mock_carrier(settings):
    from apps.core import providers

    settings.CARRIER_PROVIDER = "mock"
    providers.carrier.cache_clear()
    try:
        assert isinstance(providers.carrier(), MockCarrier)
    finally:
        providers.carrier.cache_clear()
