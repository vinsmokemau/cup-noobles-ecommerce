"""The delivery path end to end, and the mock tracking page (SPEC.md 10.10, P10-V02)."""

from datetime import UTC, datetime, timedelta

import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.orders.models import Order, OrderEvent
from apps.shipping.carriers.base import ShipmentStatus
from apps.shipping.carriers.mock import MockCarrier
from tests.factories.orders import (
    ShipmentFactory,
    order_in_state,
    order_through_checkout,
)

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def inline_post(**shipment):
    """The change form as a browser posts it, with one blank shipment row filled in."""
    data = {}
    for prefix, total in (("lines", 0), ("events", 0), ("shipments", 1)):
        data[f"{prefix}-TOTAL_FORMS"] = str(total)
        data[f"{prefix}-INITIAL_FORMS"] = "0"
        data[f"{prefix}-MIN_NUM_FORMS"] = "0"
        data[f"{prefix}-MAX_NUM_FORMS"] = "1000"
    data.update({f"shipments-0-{key}": value for key, value in shipment.items()})
    return data


def track_url(tracking_number, status=None):
    if status is None:
        return reverse("dev-carrier-track", args=[tracking_number])
    return reverse("dev-carrier-report", args=[tracking_number, status])


def test_p10_v02_delivery_end_to_end(dev_defaults, admin_client, client, clock):
    clock.travel(NOW)
    order = order_through_checkout("preparing")
    assert order.state == "preparing"

    admin_client.post(
        reverse("admin:orders_order_change", args=[order.pk]),
        inline_post(create="on", tracking_number=""),
        follow=True,
    )
    order.refresh_from_db()
    shipment = order.shipments.get()
    assert order.state == "shipped"
    assert shipment.tracking_number == f"MOCK-{order.number}-1"
    assert shipment.tracking_url.endswith(track_url(shipment.tracking_number))

    page = client.get(track_url(shipment.tracking_number))
    assert "SIMULADOR — este envío no es real" in page.content.decode()

    client.post(track_url(shipment.tracking_number, "delivered"))
    order.refresh_from_db()
    shipment.refresh_from_db()
    assert order.state == "delivered"
    assert shipment.delivered_at == NOW
    event = OrderEvent.objects.get(order=order, event="marked_delivered")
    assert event.actor == "carrier"

    clock.travel(NOW + timedelta(days=7))
    call_command("advance_orders")
    order.refresh_from_db()
    assert order.state == "completed"


def test_tracking_page_shows_history_and_the_three_buttons(client):
    order = order_in_state("shipped")
    shipment = ShipmentFactory(order=order, carrier="mock")
    MockCarrier().create_shipment(order, tracking_number=shipment.tracking_number)

    html = client.get(track_url(shipment.tracking_number)).content.decode()

    for label in ("En tránsito", "Entregado", "Incidencia"):
        assert f">{label}</button>" in html
    assert "in_transit" in html
    assert order.number in html


def test_in_transit_and_incident_buttons_leave_the_order_shipped(client):
    order = order_in_state("shipped")
    shipment = ShipmentFactory(order=order, carrier="mock")
    MockCarrier().create_shipment(order, tracking_number=shipment.tracking_number)

    for status, expected in (
        ("exception", ShipmentStatus.EXCEPTION),
        ("in_transit", ShipmentStatus.IN_TRANSIT),
    ):
        response = client.post(track_url(shipment.tracking_number, status))
        assert response.status_code == 302
        assert MockCarrier().get_status(shipment.tracking_number) is expected

    assert Order.objects.get(pk=order.pk).state == "shipped"
    statuses = [e["status"] for e in MockCarrier().history(shipment.tracking_number)]
    assert statuses == ["in_transit", "exception", "in_transit"]


def test_a_button_syncs_only_its_own_shipment(client):
    mine, other = (order_in_state("shipped") for _ in range(2))
    shipments = [ShipmentFactory(order=o, carrier="mock") for o in (mine, other)]
    for order, shipment in zip((mine, other), shipments, strict=True):
        MockCarrier().create_shipment(order, tracking_number=shipment.tracking_number)
    MockCarrier().record_status(shipments[1].tracking_number, ShipmentStatus.DELIVERED)

    client.post(track_url(shipments[0].tracking_number, "delivered"))

    assert Order.objects.get(pk=mine.pk).state == "delivered"
    assert Order.objects.get(pk=other.pk).state == "shipped"


def test_unknown_tracking_number_and_status_are_404(client):
    assert client.get(track_url("NO-EXISTE")).status_code == 404
    assert client.post(track_url("NO-EXISTE", "delivered")).status_code == 404
    order = order_in_state("shipped")
    MockCarrier().create_shipment(order, tracking_number="UNA")
    assert client.post(track_url("UNA", "perdido")).status_code == 404
