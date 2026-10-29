"""Edges of the delivery admin and the packing view that the happy-path specs leave unexercised
(SPEC.md T10.1, T10.17). Added at the Phase 10 close, so the coverage of `apps/orders` holds."""

import pytest
from django.urls import reverse

from apps.inventory.models import InventoryReservation, StockItem
from apps.orders import admin as order_admin
from apps.orders.models import Order
from apps.orders.state_machine import GuardFailed, IllegalTransition
from apps.shipping.carriers.base import TrackingNumberRequired
from tests.factories.orders import ShipmentFactory, order_through_checkout
from tests.integration.fulfillment.test_delivery_flow import inline_post

pytestmark = pytest.mark.django_db


def post_shipment(admin_client, order, **shipment):
    return admin_client.post(
        reverse("admin:orders_order_change", args=[order.pk]),
        inline_post(**shipment),
        follow=True,
    )


def messages_of(response):
    return [str(m) for m in response.context["messages"]]


def test_an_invalid_cost_is_a_field_error_and_ships_nothing(dev_defaults, admin_client):
    order = order_through_checkout("preparing")

    response = post_shipment(admin_client, order, create="on", cost="abc")

    assert response.status_code == 200
    order.refresh_from_db()
    assert order.state == "preparing"
    assert not order.shipments.exists()
    assert "El costo no es válido." in response.content.decode()


def test_a_carrier_that_cannot_generate_a_number_asks_for_one(
    dev_defaults, admin_client, monkeypatch
):
    order = order_through_checkout("preparing")

    class NoNumbers:
        def create_shipment(self, order, tracking_number=None):
            raise TrackingNumberRequired

    monkeypatch.setattr(order_admin.providers, "carrier", lambda: NoNumbers())

    response = post_shipment(admin_client, order, create="on")

    assert any("escribe el número de guía" in m for m in messages_of(response))
    order.refresh_from_db()
    assert order.state == "preparing" and not order.shipments.exists()


@pytest.mark.parametrize(
    "error",
    [
        IllegalTransition("paid", "shipment_created"),
        GuardFailed("shipment_created", "sin guía"),
    ],
)
def test_a_refused_transition_creates_no_shipment(
    dev_defaults, admin_client, monkeypatch, error
):
    order = order_through_checkout("preparing")

    def refuse(order_id, event, **kwargs):
        raise error

    monkeypatch.setattr(order_admin, "apply_event", refuse)

    response = post_shipment(admin_client, order, create="on", tracking_number="G1")

    assert any(m.startswith("No se pudo crear el envío") for m in messages_of(response))
    order.refresh_from_db()
    assert order.state == "preparing" and not order.shipments.exists()


def test_a_saved_shipment_is_shown_read_only(dev_defaults, admin_client):
    order = order_through_checkout("shipped")
    shipment = order.shipments.first() or ShipmentFactory(order=order)

    page = admin_client.get(reverse("admin:orders_order_change", args=[order.pk]))

    assert shipment.tracking_number in page.content.decode()


def test_packing_falls_back_to_the_fulfillment_source_without_a_reservation(
    dev_defaults, admin_client
):
    order = order_through_checkout("preparing")
    line = order.lines.get()
    InventoryReservation.objects.filter(order=order).delete()
    StockItem.objects.filter(variant=line.variant).update(bin_location="B-01-1")

    page = admin_client.get(reverse("admin:orders_order_packing", args=[order.pk]))

    assert [r["bin_location"] for r in page.context["lines"]] == ["B-01-1"]


def test_packing_view_of_a_missing_order_is_forbidden(admin_client):
    missing = Order.objects.order_by("-pk").values_list("pk", flat=True).first() or 0

    response = admin_client.get(
        reverse("admin:orders_order_packing", args=[missing + 1])
    )

    assert response.status_code == 403
