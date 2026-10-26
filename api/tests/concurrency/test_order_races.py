"""Order races (SPEC.md Phase 8)."""

import pytest

from apps.inventory.errors import InsufficientStock
from apps.orders.models import Order
from apps.orders.services import LinesUnavailable
from tests.concurrency import run_concurrently  # type: ignore[attr-defined]  # tests/concurrency/ is also a directory
from tests.factories.inventory import assert_stock_integrity, stocked_variant
from tests.factories.orders import cart_with, place_order

pytestmark = [pytest.mark.concurrency, pytest.mark.django_db(transaction=True)]


def test_p8_v11_crossed_carts_no_deadlock(dev_defaults):
    a = stocked_variant(1)
    b = stocked_variant(1)
    carts = [cart_with((a, 1), (b, 1)), cart_with((b, 1), (a, 1))]

    outcomes = run_concurrently(lambda i: place_order(carts[i]).number, 2)

    # Both finish: each succeeds, or is refused for stock. A deadlock would raise an
    # OperationalError (or hang the barrier) instead.
    for outcome in outcomes:
        assert outcome.error is None or isinstance(
            outcome.error, (InsufficientStock, LinesUnavailable)
        ), outcome.error
    assert len([o for o in outcomes if o.error is None]) == 1
    assert Order.objects.filter(state="pending_payment").count() == 1
    assert_stock_integrity(a)
    assert_stock_integrity(b)
