"""An order has at most one shipment (SPEC.md 10.18, P10-V27, OA-60, ADR-0051)."""

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse

from apps.orders.admin import ShipmentInline
from apps.orders.models import Order, Shipment
from tests.factories.orders import STAND_IN_ADDRESS, ShipmentFactory, order_in_state

pytestmark = pytest.mark.django_db


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


def test_p10_v27_one_shipment_per_order():
    order = order_in_state("preparing")
    ShipmentFactory(order=order)

    with pytest.raises(IntegrityError), transaction.atomic():
        ShipmentFactory(order=order)

    assert order.shipments.count() == 1
    ShipmentFactory(order=order_in_state("preparing"))  # another order is unaffected


def test_p10_v27_admin_offers_no_second_shipment(admin_client):
    order = order_in_state("preparing")
    url = reverse("admin:orders_order_change", args=[order.pk])
    assert b'name="shipments-0-create"' in admin_client.get(url).content

    ShipmentFactory(order=order)

    assert b'name="shipments-0-create"' not in admin_client.get(url).content


def test_p10_v27_admin_ignores_a_stale_post_for_a_second_shipment(admin_client):
    order = order_in_state("preparing")
    ShipmentFactory(order=order, tracking_number="PRIMERA")
    url = reverse("admin:orders_order_change", args=[order.pk])

    admin_client.post(
        url, inline_post(create="on", tracking_number="SEGUNDA"), follow=True
    )

    assert list(order.shipments.values_list("tracking_number", flat=True)) == [
        "PRIMERA"
    ]
    assert Order.objects.get(pk=order.pk).state == "preparing"


def test_p10_v27_admin_reports_a_race_for_the_second_shipment(
    admin_client, monkeypatch
):
    order = order_in_state("preparing")
    ShipmentFactory(order=order, tracking_number="PRIMERA")
    # The page was built while the order had no shipment: the form still offers the row.
    monkeypatch.setattr(ShipmentInline, "_can_ship", staticmethod(lambda order: True))
    url = reverse("admin:orders_order_change", args=[order.pk])

    response = admin_client.post(
        url, inline_post(create="on", tracking_number="SEGUNDA"), follow=True
    )

    messages = [str(m) for m in response.context["messages"]]
    assert "No se pudo crear el envío: el pedido ya tiene un envío." in messages
    assert order.shipments.count() == 1
    assert Order.objects.get(pk=order.pk).state == "preparing"


def _order_before_0002(migrator):
    state = migrator.apply_initial_migration(("orders", "0001_initial"))
    return state, _historic_order(state)


def _historic_order(state):
    return state.apps.get_model("orders", "Order").objects.create(
        number="CN-2026-900001",
        state="draft",
        email="doble@example.com",
        subtotal_cents=0,
        total_cents=0,
        fulfillment_method="delivery",
        shipping_address=STAND_IN_ADDRESS,
    )


@pytest.mark.django_db(transaction=True)
def test_p10_v27_migration_refuses_an_order_with_two_shipments(migrator):
    state, order = _order_before_0002(migrator)
    HistoricShipment = state.apps.get_model("orders", "Shipment")
    for number in ("UNA", "OTRA"):
        HistoricShipment.objects.create(
            order=order, carrier="manual", tracking_number=number
        )

    with pytest.raises(RuntimeError, match=r"CN-2026-900001 \(2\)"):
        migrator.apply_tested_migration(("orders", "0002_shipment_one_per_order"))

    assert HistoricShipment.objects.filter(order=order).count() == 2  # nothing deleted
    HistoricShipment.objects.filter(tracking_number="OTRA").delete()
    migrator.reset()


@pytest.mark.django_db(transaction=True)
def test_p10_v27_migration_runs_forward_and_backward_on_clean_data(migrator):
    state, order = _order_before_0002(migrator)
    state.apps.get_model("orders", "Shipment").objects.create(
        order=order, carrier="manual", tracking_number="UNA"
    )

    migrator.apply_tested_migration(("orders", "0002_shipment_one_per_order"))
    with pytest.raises(IntegrityError), transaction.atomic():
        Shipment.objects.create(
            order_id=order.pk, carrier="manual", tracking_number="OTRA"
        )

    # Backward the index is plain again: the same order takes two shipments.
    back = migrator.apply_initial_migration(("orders", "0001_initial"))
    HistoricShipment = back.apps.get_model("orders", "Shipment")
    reopened = _historic_order(back)
    for number in ("UNA", "OTRA"):
        HistoricShipment.objects.create(
            order=reopened, carrier="manual", tracking_number=number
        )
    assert HistoricShipment.objects.filter(order=reopened).count() == 2
    HistoricShipment.objects.filter(tracking_number="OTRA").delete()
    migrator.reset()
