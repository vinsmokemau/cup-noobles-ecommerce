"""Order races (SPEC.md Phase 8)."""

from datetime import timedelta

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


def test_p8_v04_approve_vs_deadline(clock, dev_defaults):
    from apps.inventory.management.commands.expire_reservations import expire_order
    from apps.inventory.models import StockItem
    from apps.orders.state_machine import IllegalTransition, apply_event

    variant = stocked_variant(5)
    order = place_order(cart_with((variant, 2)))
    clock.travel(order.payment_deadline_at + timedelta(minutes=1))

    def racer(index):
        if index == 0:
            return apply_event(
                order.pk, "payment_approved", amount_cents=order.total_cents
            ).state
        return expire_order(order.pk)

    outcomes = run_concurrently(racer, 2)

    order.refresh_from_db()
    item = StockItem.objects.get(variant=variant)
    approve, expire = outcomes
    assert order.state in ("paid", "expired")
    if order.state == "paid":
        assert (approve.error, expire.error, expire.value) == (None, None, False)
        assert (item.on_hand, item.reserved) == (3, 0)
    else:
        assert isinstance(approve.error, IllegalTransition)
        assert (expire.error, expire.value) == (None, True)
        assert (item.on_hand, item.reserved) == (5, 0)
    assert order.events.exclude(event="checkout_submitted").count() == 1
    assert_stock_integrity(variant)


def test_two_advance_orders_runs_complete_an_order_once(clock):
    from datetime import UTC, datetime

    from apps.orders.management.commands.advance_orders import (
        complete_delivered_orders,
    )
    from apps.orders.models import OrderEvent
    from tests.factories.orders import ShipmentFactory, order_in_state

    delivered_at = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    order = order_in_state("delivered")
    ShipmentFactory(order=order, delivered_at=delivered_at)
    clock.travel(delivered_at + timedelta(days=8))

    outcomes = run_concurrently(lambda i: complete_delivered_orders(), 2)

    assert [o.error for o in outcomes] == [None, None]
    assert sorted(o.value for o in outcomes) == [0, 1]
    assert Order.objects.get(pk=order.pk).state == "completed"
    assert OrderEvent.objects.filter(order=order, event="auto_after_7d").count() == 1
