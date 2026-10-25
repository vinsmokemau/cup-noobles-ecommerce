from datetime import timedelta

import pytest
from django.db import transaction

from apps.inventory import services
from apps.inventory.management.commands.expire_reservations import expire_order
from apps.inventory.models import InventoryReservation, StockItem, StockLedger
from apps.orders.models import Order
from tests.concurrency import run_concurrently  # type: ignore[attr-defined]  # tests/concurrency/ is also a directory
from tests.factories.inventory import (
    assert_stock_integrity,
    holding_order,
    stocked_variant,
)

pytestmark = [pytest.mark.concurrency, pytest.mark.django_db(transaction=True)]

LAPSED = timedelta(seconds=-1)


def test_two_expiry_runs_release_a_hold_once():
    variant = stocked_variant(on_hand=5)
    order = holding_order(variant, 2, ttl=LAPSED)

    outcomes = run_concurrently(lambda i: expire_order(order.pk), 2)

    assert [o.error for o in outcomes] == [None, None]
    assert sorted(o.value for o in outcomes) == [False, True]
    assert StockItem.objects.get(variant=variant).reserved == 0
    assert_stock_integrity(variant)


def test_expiry_racing_a_payment_settles_the_hold_exactly_once():
    variant = stocked_variant(on_hand=5)
    order = holding_order(variant, 2, ttl=LAPSED)

    def settle(index):
        if index == 0:
            # What the webhook does: lock the order, then commit its holds.
            with transaction.atomic():
                Order.objects.select_for_update().get(pk=order.pk)
                services.commit_reservations(order)
        else:
            expire_order(order.pk)

    outcomes = run_concurrently(settle, 2)

    assert [o.error for o in outcomes] == [None, None]
    reservation = InventoryReservation.objects.get(order=order)
    item = StockItem.objects.get(variant=variant)
    sales = StockLedger.objects.filter(stock_item=item, reason="sale_online").count()
    if reservation.state == "committed":
        assert (item.on_hand, item.reserved, sales) == (3, 0, 1)
    else:
        assert (reservation.state, item.on_hand, item.reserved, sales) == (
            "released",
            5,
            0,
            0,
        )
    assert_stock_integrity(variant)
