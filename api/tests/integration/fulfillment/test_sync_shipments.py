"""`sync_shipments`: carrier status to T11 (SPEC.md 10.11, §4.8, P10-V19, REQ-022)."""

import logging
from datetime import UTC, datetime, timedelta

import pytest
from django.core.management import call_command

from apps.orders.models import Order, OrderEvent
from apps.shipping.carriers.base import ShipmentStatus
from apps.shipping.carriers.mock import MockCarrier
from tests.factories.orders import ShipmentFactory, order_in_state

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def shipped_order_with_shipment(status=ShipmentStatus.IN_TRANSIT):
    order = order_in_state("shipped")
    shipment = ShipmentFactory(order=order, carrier="mock")
    report(shipment, status)
    return order, shipment


def report(shipment, status):
    """What the mock carrier will answer for this shipment from now on."""
    MockCarrier()._write(
        shipment.tracking_number,
        {
            "tracking_number": shipment.tracking_number,
            "status": status.value,
            "events": [],
        },
    )


def events_of(order):
    return list(OrderEvent.objects.filter(order=order, event="marked_delivered"))


def test_p10_v19_sync_never_regresses_delivered(clock):
    order, shipment = shipped_order_with_shipment()
    clock.travel(NOW)
    report(shipment, ShipmentStatus.DELIVERED)
    call_command("sync_shipments")

    report(shipment, ShipmentStatus.IN_TRANSIT)
    clock.travel(NOW + timedelta(hours=1))
    call_command("sync_shipments")

    shipment.refresh_from_db()
    order.refresh_from_db()
    assert shipment.delivered_at == NOW
    assert order.state == "delivered"
    assert len(events_of(order)) == 1


def test_delivered_report_fires_t11_once_with_the_carrier_as_actor(clock):
    order, shipment = shipped_order_with_shipment(ShipmentStatus.DELIVERED)
    clock.travel(NOW)

    call_command("sync_shipments")
    call_command("sync_shipments")

    shipment.refresh_from_db()
    order.refresh_from_db()
    assert order.state == "delivered"
    assert shipment.delivered_at == NOW
    (event,) = events_of(order)
    assert event.actor == "carrier"


def test_in_transit_and_unknown_change_nothing():
    in_transit, _ = shipped_order_with_shipment(ShipmentStatus.IN_TRANSIT)
    unknown = order_in_state("shipped")
    ShipmentFactory(order=unknown, carrier="mock")  # the mock store has never seen it

    call_command("sync_shipments")

    assert Order.objects.get(pk=in_transit.pk).state == "shipped"
    assert Order.objects.get(pk=unknown.pk).state == "shipped"
    assert not OrderEvent.objects.filter(event="marked_delivered").exists()


def test_exception_alerts_without_a_transition(caplog):
    order, shipment = shipped_order_with_shipment(ShipmentStatus.EXCEPTION)

    with caplog.at_level(logging.ERROR):
        call_command("sync_shipments")

    shipment.refresh_from_db()
    assert Order.objects.get(pk=order.pk).state == "shipped"
    assert shipment.delivered_at is None
    assert shipment.tracking_number in caplog.text


def test_staff_t11_then_sync_adds_no_second_transition(clock):
    from apps.orders.state_machine import apply_event

    order, shipment = shipped_order_with_shipment(ShipmentStatus.DELIVERED)
    apply_event(order, "marked_delivered", actor="staff")

    call_command("sync_shipments")

    assert [e.actor for e in events_of(order)] == ["staff"]


def test_only_shipped_orders_are_synced():
    order = order_in_state("preparing")
    shipment = ShipmentFactory(order=order, carrier="mock")
    report(shipment, ShipmentStatus.DELIVERED)

    call_command("sync_shipments")

    assert Order.objects.get(pk=order.pk).state == "preparing"
    assert not OrderEvent.objects.filter(event="marked_delivered").exists()


def test_a_failing_shipment_does_not_stop_the_others(monkeypatch):
    from django.core.management.base import CommandError

    _, broken = shipped_order_with_shipment(ShipmentStatus.DELIVERED)
    good, _ = shipped_order_with_shipment(ShipmentStatus.DELIVERED)
    real = MockCarrier.get_status

    def flaky(self, tracking_number):
        if tracking_number == broken.tracking_number:
            raise RuntimeError("carrier down")
        return real(self, tracking_number)

    monkeypatch.setattr(MockCarrier, "get_status", flaky)

    with pytest.raises(CommandError):
        call_command("sync_shipments")

    assert Order.objects.get(pk=good.pk).state == "delivered"
