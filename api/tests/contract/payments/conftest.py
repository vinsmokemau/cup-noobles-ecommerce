import re
from datetime import UTC, datetime

import pytest
from django.core.cache import cache

from tests.contract.payments.driver import MockDriver
from tests.factories.inventory import stocked_variant
from tests.factories.orders import cart_with, place_order

QUANTITY = 2
CHECKOUT = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _fresh_rate_limit_counters():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def driver(request):
    """The driver under test. Phase 16 adds the Mercado Pago sandbox driver here.

    A scenario the driver can't play is skipped with the driver's reason, naming its PAY ID.
    """
    driver = MockDriver()
    scenario = re.match(r"test_(pay)_(\d\d)_", request.node.name)
    if scenario:
        pay_id = f"PAY-{scenario.group(2)}"
        supported = driver.supports(pay_id)
        if supported is not True:
            pytest.skip(f"{pay_id}: {driver.name} cannot drive it: {supported}")
    return driver


@pytest.fixture
def variant(db):
    return stocked_variant(10)


@pytest.fixture
def shop(dev_defaults, clock):
    """A frozen clock at checkout time, with the shipping zones a real checkout needs."""
    clock.travel(CHECKOUT)
    return clock


@pytest.fixture
def order(shop, variant):
    """A `pending_payment` order from a real checkout: stock held, payment `initiated`."""
    return place_order(cart_with((variant, QUANTITY)))
