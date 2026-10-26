"""`advance_orders`: auto-completion (SPEC.md 8.A T12, §4.8, P8-V13, P8-V14)."""

from datetime import UTC, datetime, timedelta

import pytest
from django.core.management import call_command

from apps.orders.models import Order, OrderEvent
from tests.factories.orders import ShipmentFactory, order_in_state

pytestmark = pytest.mark.django_db

DELIVERED_AT = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
WEEK = timedelta(days=7)


def delivered_order(delivered_at=DELIVERED_AT):
    order = order_in_state("delivered")
    ShipmentFactory(order=order, delivered_at=delivered_at)
    return order


def state_of(order):
    return Order.objects.get(pk=order.pk).state


def test_p8_v13_auto_completion_boundaries(clock):
    order = delivered_order()

    clock.travel(DELIVERED_AT + WEEK - timedelta(seconds=1))
    call_command("advance_orders")
    assert state_of(order) == "delivered"

    clock.travel(DELIVERED_AT + WEEK)
    call_command("advance_orders")
    order.refresh_from_db()
    assert order.state == "completed"
    assert order.completed_at == DELIVERED_AT + WEEK


def test_p8_v14_advance_orders_idempotent(clock):
    due = delivered_order()
    not_yet = delivered_order(DELIVERED_AT + timedelta(days=1))
    clock.travel(DELIVERED_AT + WEEK + timedelta(hours=1))

    call_command("advance_orders")
    first = {o.pk: o.state for o in Order.objects.filter(pk__in=[due.pk, not_yet.pk])}
    events = OrderEvent.objects.count()
    call_command("advance_orders")

    assert first == {due.pk: "completed", not_yet.pk: "delivered"}
    assert {
        o.pk: o.state for o in Order.objects.filter(pk__in=[due.pk, not_yet.pk])
    } == first
    assert OrderEvent.objects.count() == events
    assert due.events.get().event == "auto_after_7d"


def test_completion_waits_for_the_last_delivered_shipment(clock):
    order = delivered_order()
    ShipmentFactory(order=order, delivered_at=DELIVERED_AT + timedelta(days=2))

    clock.travel(DELIVERED_AT + WEEK + timedelta(days=1))
    call_command("advance_orders")
    assert state_of(order) == "delivered"

    clock.travel(DELIVERED_AT + timedelta(days=9))
    call_command("advance_orders")
    assert state_of(order) == "completed"


def test_orders_in_other_states_are_left_alone(clock):
    shipped = order_in_state("shipped")
    ShipmentFactory(order=shipped, delivered_at=DELIVERED_AT)
    refunded = order_in_state("refunded")
    ShipmentFactory(order=refunded, delivered_at=DELIVERED_AT)
    undelivered = order_in_state("delivered")
    ShipmentFactory(order=undelivered, delivered_at=None)

    clock.travel(DELIVERED_AT + timedelta(days=30))
    call_command("advance_orders")

    assert [state_of(o) for o in (shipped, refunded, undelivered)] == [
        "shipped",
        "refunded",
        "delivered",
    ]
    assert not OrderEvent.objects.exists()
