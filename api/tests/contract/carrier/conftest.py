import re
from pathlib import Path

import pytest
from django.conf import settings

from apps.orders.models import Order
from tests.contract.carrier.driver import MockDriver
from tests.factories.orders import ShipmentFactory, order_in_state


@pytest.fixture
def driver(request):
    """The driver under test. Phase 19 adds the manual carrier's driver here.

    A scenario the driver can't play is skipped with the driver's reason, naming its CAR ID.
    """
    driver = MockDriver()
    scenario = re.match(r"test_car_(\d\d)_", request.node.name)
    if scenario:
        car_id = f"CAR-{scenario.group(1)}"
        supported = driver.supports(car_id)
        if supported is not True:
            pytest.skip(f"{car_id}: {driver.name} cannot drive it: {supported}")
    return driver


@pytest.fixture
def mock_carrier_store() -> Path:
    """The mock carrier's folder. It is per test: `tests/conftest.py` points `MOCK_STORE_DIR`
    at a temporary directory."""
    return Path(settings.MOCK_STORE_DIR) / "carrier"


@pytest.fixture
def shipped_order(db, driver) -> Order:
    """A `shipped` order with its one shipment, created through the carrier under test."""
    order = order_in_state("shipped")
    ref = driver.create_shipment(order)
    ShipmentFactory(
        order=order,
        carrier=ref.carrier,
        tracking_number=ref.tracking_number,
        tracking_url=ref.tracking_url,
    )
    return order
