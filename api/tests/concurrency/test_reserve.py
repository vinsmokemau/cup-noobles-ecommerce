from datetime import timedelta

import pytest

from apps.inventory import services
from apps.inventory.errors import InsufficientStock
from apps.inventory.models import InventoryReservation, StockItem
from tests.concurrency import run_concurrently  # type: ignore[attr-defined]  # tests/concurrency/ is also a directory
from tests.factories.inventory import assert_stock_integrity, stocked_variant
from tests.factories.orders import DraftOrderFactory

pytestmark = [pytest.mark.concurrency, pytest.mark.django_db(transaction=True)]


def test_p4_v01_concurrent_reserve_last_unit():
    variant = stocked_variant(on_hand=1)
    orders = [DraftOrderFactory(), DraftOrderFactory()]

    outcomes = run_concurrently(
        lambda i: services.reserve(orders[i], [(variant, 1)], ttl=timedelta(hours=1)), 2
    )

    errors = [o.error for o in outcomes if o.error is not None]
    assert len(errors) == 1
    assert isinstance(errors[0], InsufficientStock)
    assert len([o for o in outcomes if o.error is None]) == 1
    assert (
        InventoryReservation.objects.filter(variant=variant, state="held").count() == 1
    )
    assert StockItem.objects.get(variant=variant).reserved == 1
    assert_stock_integrity(variant)
