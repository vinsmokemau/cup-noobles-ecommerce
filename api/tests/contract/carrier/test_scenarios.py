"""Carrier contract scenarios CAR-01 to CAR-07 (SPEC.md 10.13, T10.13).

Each scenario is written against `CarrierDriver` and goes through the real `sync_shipments` and
the real state machine. Only the driver differs between carriers. Sockets stay disabled (CR-41).
"""

import logging

import pytest

from apps.orders.models import Order, OrderEvent
from apps.orders.state_machine import apply_event
from apps.shipping.carriers.base import (
    ShipmentRef,
    ShipmentStatus,
    TrackingNumberRequired,
)
from tests.factories.orders import OrderFactory, ShipmentFactory, order_in_state

pytestmark = pytest.mark.django_db


def reload(order):
    return Order.objects.get(pk=order.pk)


def deliveries(order):
    return list(OrderEvent.objects.filter(order=order, event="marked_delivered"))


def tracking_number_of(order) -> str:
    return order.shipments.get().tracking_number


def test_car_01_create_with_a_given_tracking_number(driver):
    ref = driver.create_shipment(OrderFactory(), tracking_number="GUIA-0001")

    assert isinstance(ref, ShipmentRef)
    assert ref.tracking_number == "GUIA-0001"
    assert ref.carrier
    assert ref.tracking_url


def test_car_02_create_without_a_tracking_number(driver):
    order = OrderFactory(number="CN-2026-000042")

    try:
        first = driver.create_shipment(order)
    except TrackingNumberRequired:
        # A carrier that can't generate a number: staff must type it, and nothing is created
        # without it (T10.1). The manual carrier's driver plays this branch in Phase 19.
        assert order.shipments.count() == 0
        return

    assert first.tracking_number
    assert first.tracking_url
    # Deterministic: the same order asks again and gets the same number.
    assert driver.create_shipment(order).tracking_number == first.tracking_number


def test_car_03_status_of_a_new_shipment(driver, shipped_order):
    status = driver.status(tracking_number_of(shipped_order))

    assert isinstance(status, ShipmentStatus)
    # Never raises, whatever the number.
    assert isinstance(driver.status("NO-SUCH-NUMBER"), ShipmentStatus)


def test_car_04_delivered_fires_t11_once(driver, shipped_order):
    driver.report(tracking_number_of(shipped_order), ShipmentStatus.DELIVERED)

    first = driver.sync()
    second = driver.sync()

    assert (first.delivered, second.delivered) == (1, 0)
    assert reload(shipped_order).state == "delivered"
    (event,) = deliveries(shipped_order)
    assert event.actor == "carrier"
    assert shipped_order.shipments.get().delivered_at is not None


def test_car_05_exception_alerts_without_a_transition(driver, shipped_order, caplog):
    number = tracking_number_of(shipped_order)
    driver.report(number, ShipmentStatus.EXCEPTION)

    with caplog.at_level(logging.ERROR):
        result = driver.sync()

    assert result.exceptions == [number]
    assert number in caplog.text
    assert reload(shipped_order).state == "shipped"
    assert shipped_order.shipments.get().delivered_at is None
    assert deliveries(shipped_order) == []


def test_car_06_unknown_tracking_number(driver):
    order = order_in_state("shipped")
    ShipmentFactory(order=order, tracking_number="NEVER-SEEN-1")

    result = driver.sync()

    assert driver.status("NEVER-SEEN-1") is ShipmentStatus.UNKNOWN
    assert (result.checked, result.delivered, result.failed) == (1, 0, 0)
    assert reload(order).state == "shipped"
    assert deliveries(order) == []


def test_car_07_staff_t11_then_sync_adds_no_second_transition(driver, shipped_order):
    apply_event(shipped_order, "marked_delivered", actor="staff")
    driver.report(tracking_number_of(shipped_order), ShipmentStatus.DELIVERED)

    result = driver.sync()

    assert result.delivered == 0
    assert [event.actor for event in deliveries(shipped_order)] == ["staff"]
    assert reload(shipped_order).state == "delivered"
