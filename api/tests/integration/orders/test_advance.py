"""`advance_orders`: auto-completion (SPEC.md 8.A T12, §4.8, P8-V13, P8-V14), the move of
paid delivery orders to `preparing` (T7; G75, ADR-0075) and the `--order` option (G79)."""

from datetime import UTC, datetime, timedelta

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.orders.models import Order, OrderEvent
from tests.factories.inventory import LocationFactory
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
    order = delivered_order(DELIVERED_AT + timedelta(days=2))

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


def test_g75_paid_delivery_orders_move_to_preparing():
    paid = order_in_state("paid")
    second = order_in_state("paid")

    call_command("advance_orders")

    assert [state_of(paid), state_of(second)] == ["preparing", "preparing"]
    event = paid.events.get()
    assert (event.event, event.from_state, event.to_state, event.actor) == (
        "auto",
        "paid",
        "preparing",
        "system",
    )

    # A second run finds nothing to move.
    events = OrderEvent.objects.count()
    call_command("advance_orders")
    assert OrderEvent.objects.count() == events


def test_g75_only_paid_delivery_orders_are_moved():
    waiting = order_in_state("pending_payment")
    # A pickup order is Release 2 (T8): the job leaves it for that release.
    pickup = order_in_state(
        "paid", fulfillment_method="pickup", pickup_location=LocationFactory()
    )
    preparing = order_in_state("preparing")
    cancelled = order_in_state("cancelled")

    call_command("advance_orders")

    assert [state_of(o) for o in (waiting, pickup, preparing, cancelled)] == [
        "pending_payment",
        "paid",
        "preparing",
        "cancelled",
    ]
    assert not OrderEvent.objects.exists()


def test_g75_an_order_the_job_moved_can_still_be_cancelled_refunded_or_shipped():
    """T16, T17 and T10 start from `preparing` too, so moving the order early closes no door."""
    from apps.orders.state_machine import TRANSITIONS

    assert ("preparing", "cancelled_by_staff") in TRANSITIONS
    assert ("preparing", "refund_issued") in TRANSITIONS
    assert ("preparing", "shipment_created") in TRANSITIONS


def test_g75_one_failing_order_does_not_stop_the_run(monkeypatch, caplog):
    from apps.orders.management.commands import advance_orders

    broken = order_in_state("paid")
    healthy = order_in_state("paid")
    assert broken.pk < healthy.pk  # the run reaches the broken order first

    real_apply_event = advance_orders.apply_event

    def apply_event(order_id, event, **kwargs):
        if order_id == broken.pk:
            raise RuntimeError("boom")
        return real_apply_event(order_id, event, **kwargs)

    monkeypatch.setattr(advance_orders, "apply_event", apply_event)

    with caplog.at_level("ERROR", logger=advance_orders.__name__):
        prepared = advance_orders.prepare_paid_orders()

    assert prepared == 1
    assert state_of(healthy) == "preparing"
    assert state_of(broken) == "paid"
    assert f"Order {broken.pk} could not be moved to preparing" in caplog.text


def test_g47_one_failing_order_does_not_stop_the_run(clock, monkeypatch, caplog):
    from apps.orders.management.commands import advance_orders

    broken = delivered_order()
    healthy = delivered_order()
    assert broken.pk < healthy.pk  # the run reaches the broken order first
    clock.travel(DELIVERED_AT + WEEK)

    real_apply_event = advance_orders.apply_event

    def apply_event(order_id, event, **kwargs):
        if order_id == broken.pk:
            raise RuntimeError("boom")
        return real_apply_event(order_id, event, **kwargs)

    monkeypatch.setattr(advance_orders, "apply_event", apply_event)

    with caplog.at_level("ERROR", logger=advance_orders.__name__):
        completed = advance_orders.complete_delivered_orders()

    assert completed == 1
    assert state_of(healthy) == "completed"
    assert state_of(broken) == "delivered"
    assert f"Order {broken.pk} could not be completed" in caplog.text


def test_g79_only_the_named_paid_order_moves_to_preparing():
    named = order_in_state("paid")
    other = order_in_state("paid")

    call_command("advance_orders", "--order", named.number)

    assert [state_of(named), state_of(other)] == ["preparing", "paid"]
    assert OrderEvent.objects.get().order_id == named.pk

    # Without the option the job is unchanged: it moves the order that was left out.
    call_command("advance_orders")
    assert state_of(other) == "preparing"


def test_g79_only_the_named_delivered_order_completes(clock):
    named = delivered_order()
    other = delivered_order()
    clock.travel(DELIVERED_AT + WEEK)

    call_command("advance_orders", "--order", named.number)

    assert [state_of(named), state_of(other)] == ["completed", "delivered"]
    assert OrderEvent.objects.get().order_id == named.pk


def test_g79_the_named_order_is_left_alone_when_it_is_not_due(clock):
    waiting = order_in_state("pending_payment")
    early = delivered_order()
    clock.travel(DELIVERED_AT + WEEK - timedelta(seconds=1))

    call_command("advance_orders", "--order", waiting.number)
    call_command("advance_orders", "--order", early.number)

    assert [state_of(waiting), state_of(early)] == ["pending_payment", "delivered"]
    assert not OrderEvent.objects.exists()


def test_g79_an_unknown_order_number_fails():
    paid = order_in_state("paid")

    with pytest.raises(CommandError, match="There is no order CN-0000-000000"):
        call_command("advance_orders", "--order", "CN-0000-000000")

    # Nothing ran: the order every plain run would move is where it was.
    assert state_of(paid) == "paid"
    assert not OrderEvent.objects.exists()
