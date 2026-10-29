"""The reporting exports of orders, order lines and shipments (SPEC.md T10.16, P10-V25, REQ-063)."""

import csv
import io
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from django.urls import reverse

from tests.factories.orders import OrderLineFactory, ShipmentFactory, order_in_state
from tests.factories.payments import PaymentFactory

pytestmark = pytest.mark.django_db

MEXICO = ZoneInfo("America/Mexico_City")
URL = "admin:orders_order_reports"


def local(day, hour=12, minute=0, second=0):
    return datetime(2026, 10, day, hour, minute, second, tzinfo=MEXICO)


def export(client, report, start, end):
    response = client.get(reverse(URL), {"report": report, "start": start, "end": end})
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert "attachment" in response["Content-Disposition"]
    return list(csv.DictReader(io.StringIO(response.content.decode())))


def test_p10_v25_csv_exports(admin_client):
    shipped = order_in_state(
        "shipped",
        placed_at=local(10, 9),
        paid_at=local(10, 10),
        shipped_at=local(11, 15),
        subtotal_cents=20000,
        shipping_cents=9900,
        total_cents=29900,
        tax_included_cents=4124,
    )
    PaymentFactory(order=shipped, status="approved", method="spei")
    costed = OrderLineFactory(
        order=shipped,
        sku="SKU-A",
        product_name="Mazo",
        quantity=2,
        unit_price_cents=10000,
        unit_cost_cents=6500,
    )
    uncosted = OrderLineFactory(
        order=shipped,
        sku="SKU-B",
        product_name="Funda",
        unit_cost_cents=None,
        is_preorder=True,
    )
    ShipmentFactory(
        order=shipped,
        carrier="manual",
        tracking_number="G123",
        cost_cents=8000,
        shipped_at=local(11, 15),
        delivered_at=local(13, 8),
    )
    cancelled = order_in_state(
        "cancelled",
        placed_at=local(11, 9),
        cancelled_at=local(11, 20),
        cancel_reason="Sin existencias",
    )
    OrderLineFactory(order=cancelled, sku="SKU-C", unit_cost_cents=0)
    order_in_state("draft")  # never placed
    order_in_state("paid", placed_at=local(9, 23, 59, 59))  # the second before
    order_in_state("paid", placed_at=local(14, 0, 0, 0))  # the first second after

    orders = export(admin_client, "orders", "2026-10-10", "2026-10-13")
    assert [r["order_number"] for r in orders] == [shipped.number, cancelled.number]
    row = orders[0]
    assert list(row) == [
        "order_number",
        "state",
        "fulfillment_method",
        "payment_method",
        "placed_at",
        "paid_at",
        "shipped_at",
        "completed_at",
        "cancelled_at",
        "cancel_reason",
        "subtotal_cents",
        "shipping_cents",
        "discount_cents",
        "total_cents",
        "tax_included_cents",
    ]
    assert row["placed_at"] == "2026-10-10T09:00:00-06:00"
    assert row["paid_at"] == "2026-10-10T10:00:00-06:00"
    assert row["shipped_at"] == "2026-10-11T15:00:00-06:00"
    assert row["payment_method"] == "spei"
    assert (row["subtotal_cents"], row["shipping_cents"], row["total_cents"]) == (
        "20000",
        "9900",
        "29900",
    )
    assert row["tax_included_cents"] == "4124"
    assert orders[1]["cancel_reason"] == "Sin existencias"
    assert orders[1]["paid_at"] == "" and orders[1]["payment_method"] == ""

    lines = export(admin_client, "lines", "2026-10-10", "2026-10-13")
    assert [r["sku"] for r in lines] == ["SKU-A", "SKU-B", "SKU-C"]
    assert list(lines[0]) == [
        "order_number",
        "order_state",
        "placed_at",
        "sku",
        "product_name",
        "quantity",
        "unit_price_cents",
        "line_total_cents",
        "unit_cost_cents",
        "is_preorder",
    ]
    assert lines[0]["order_number"] == shipped.number
    assert lines[0]["order_state"] == "shipped"
    assert (lines[0]["quantity"], lines[0]["line_total_cents"]) == ("2", "20000")
    assert lines[0]["unit_cost_cents"] == str(costed.unit_cost_cents) == "6500"
    assert lines[1]["unit_cost_cents"] == "" and lines[1]["is_preorder"] == "true"
    assert uncosted.unit_cost_cents is None
    assert lines[2]["unit_cost_cents"] == "0"  # a zero cost is not a missing one

    shipments = export(admin_client, "shipments", "2026-10-10", "2026-10-13")
    assert len(shipments) == 1
    assert list(shipments[0]) == [
        "order_number",
        "order_state",
        "paid_at",
        "carrier",
        "tracking_number",
        "cost_cents",
        "shipped_at",
        "delivered_at",
    ]
    assert shipments[0]["order_number"] == shipped.number
    assert shipments[0]["paid_at"] == "2026-10-10T10:00:00-06:00"
    assert shipments[0]["cost_cents"] == "8000"
    assert shipments[0]["shipped_at"] == "2026-10-11T15:00:00-06:00"
    assert shipments[0]["delivered_at"] == "2026-10-13T08:00:00-06:00"


def test_shipments_are_in_range_by_their_own_shipped_date(admin_client):
    order = order_in_state("shipped", placed_at=local(1), paid_at=local(1))
    ShipmentFactory(order=order, shipped_at=local(20), delivered_at=None)

    assert export(admin_client, "shipments", "2026-10-01", "2026-10-19") == []
    rows = export(admin_client, "shipments", "2026-10-20", "2026-10-20")
    assert [r["delivered_at"] for r in rows] == [""]


def test_a_cell_that_starts_like_a_formula_is_neutralised(admin_client):
    order = order_in_state("paid", placed_at=local(10), cancel_reason="=1+1")
    OrderLineFactory(order=order, product_name="@SUM(A1)", sku="-X")

    assert (
        export(admin_client, "orders", "2026-10-10", "2026-10-10")[0]["cancel_reason"]
        == "'=1+1"
    )
    line = export(admin_client, "lines", "2026-10-10", "2026-10-10")[0]
    assert (line["product_name"], line["sku"]) == ("'@SUM(A1)", "'-X")


def test_the_range_must_be_valid_and_the_exports_are_staff_only(
    admin_client, client, django_user_model
):
    backwards = admin_client.get(
        reverse(URL), {"report": "orders", "start": "2026-10-13", "end": "2026-10-10"}
    )
    assert backwards.status_code == 200
    assert "end" in backwards.context["form"].errors
    assert not backwards.get("Content-Type", "").startswith("text/csv")

    unknown = admin_client.get(
        reverse(URL),
        {"report": "customers", "start": "2026-10-10", "end": "2026-10-10"},
    )
    assert "report" in unknown.context["form"].errors

    assert admin_client.get(reverse(URL)).status_code == 200
    query = {"report": "orders", "start": "2026-10-10", "end": "2026-10-13"}
    assert client.get(reverse(URL), query).status_code == 302

    customer = django_user_model.objects.create_user("cliente", password="x")
    client.force_login(customer)
    assert client.get(reverse(URL), query).status_code == 302

    staff = django_user_model.objects.create_user(
        "sin-permisos", password="x", is_staff=True
    )
    client.force_login(staff)
    assert client.get(reverse(URL), query).status_code == 403
