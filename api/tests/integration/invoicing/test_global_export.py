"""The global-invoice export (SPEC.md T10.15, P10-V24, REQ-060)."""

import csv
import io
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from django.urls import reverse
from django.utils import timezone

from tests.factories.invoicing import InvoiceRequestFactory
from tests.factories.orders import order_in_state
from tests.factories.payments import PaymentFactory

pytestmark = pytest.mark.django_db

MEXICO = ZoneInfo("America/Mexico_City")
URL = "admin:invoicing_invoicerequest_global_export"


def local(day, hour=12, minute=0, second=0):
    return datetime(2026, 10, day, hour, minute, second, tzinfo=MEXICO)


def paid_order(paid_at, state="paid", method="credit_card", **fields):
    order = order_in_state(state, paid_at=paid_at, **fields)
    PaymentFactory(order=order, status="approved", method=method)
    return order


def export(client, start, end):
    response = client.get(reverse(URL), {"start": start, "end": end})
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    return list(csv.DictReader(io.StringIO(response.content.decode())))


def test_p10_v24_global_invoice_export(admin_client):
    listed = paid_order(
        local(10),
        method="spei",
        subtotal_cents=11600,
        total_cents=11600,
        tax_included_cents=1600,
    )
    no_request = paid_order(
        local(11), subtotal_cents=5000, total_cents=5000, tax_included_cents=690
    )
    requested = paid_order(local(12))
    InvoiceRequestFactory(order=requested)
    cancelled_cfdi = paid_order(local(12, 13))
    InvoiceRequestFactory(
        order=cancelled_cfdi, status="cancelled", cancelled_at=timezone.now()
    )
    issued = paid_order(local(12, 14))
    InvoiceRequestFactory(
        order=issued, status="issued", issued_at=timezone.now(), cfdi_uuid=uuid4()
    )
    paid_order(local(12, 15), state="cancelled")
    paid_order(local(12, 16), state="expired")
    order_in_state("pending_payment")
    paid_order(local(9, 23, 59, 59))  # the second before the range opens
    paid_order(local(14, 0, 0, 0))  # the first second after it closes
    first_second = paid_order(local(10, 0, 0, 0))
    last_second = paid_order(local(13, 23, 59, 59))

    rows = export(admin_client, "2026-10-10", "2026-10-13")

    assert [r["order_number"] for r in rows] == [
        first_second.number,
        listed.number,
        no_request.number,
        requested.number,
        cancelled_cfdi.number,
        last_second.number,
    ]
    by_number = {r["order_number"]: r for r in rows}
    row = by_number[listed.number]
    assert row["paid_at"] == "2026-10-10T12:00:00-06:00"
    assert row["payment_method"] == "spei"
    assert row["total_cents"] == "11600"
    assert row["tax_included_cents"] == "1600"
    assert by_number[no_request.number]["tax_included_cents"] == "690"
    assert list(rows[0]) == [
        "order_number",
        "paid_at",
        "payment_method",
        "total_cents",
        "tax_included_cents",
    ]


def test_an_order_with_no_settled_payment_has_an_empty_method(admin_client):
    order = order_in_state("paid", paid_at=local(10))
    PaymentFactory(order=order, status="rejected", method="credit_card")

    rows = export(admin_client, "2026-10-10", "2026-10-10")

    assert [(r["order_number"], r["payment_method"]) for r in rows] == [
        (order.number, "")
    ]


def test_the_range_must_be_valid_and_the_export_is_staff_only(admin_client, client):
    backwards = admin_client.get(
        reverse(URL), {"start": "2026-10-13", "end": "2026-10-10"}
    )
    assert backwards.status_code == 200
    assert "end" in backwards.context["form"].errors
    assert not backwards.get("Content-Type", "").startswith("text/csv")

    assert admin_client.get(reverse(URL)).status_code == 200
    anonymous = client.get(reverse(URL), {"start": "2026-10-10", "end": "2026-10-13"})
    assert anonymous.status_code == 302
