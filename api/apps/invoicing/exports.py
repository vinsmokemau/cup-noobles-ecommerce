"""The global-invoice export, "Exportar para factura global" (SPEC.md T10.15, A8, D16).

One row per order paid in a date range that has no issued CFDI. The range is two calendar dates
in the store timezone (G5), both included. The period the accountant uses and how refunds after
an export are handled are D16; the export decides neither.
"""

from __future__ import annotations

import csv
from datetime import date, datetime, time, timedelta
from typing import TextIO

from django.db.models import OuterRef, QuerySet, Subquery

from apps.invoicing.models import InvoiceRequest
from apps.orders.models import Order
from apps.orders.numbering import STORE_TIMEZONE
from apps.payments.models import Payment

COLUMNS = (
    "order_number",
    "paid_at",
    "payment_method",
    "total_cents",
    "tax_included_cents",
)

# A payment that never settled is not the one the customer paid with.
_UNSETTLED = ("initiated", "pending", "rejected", "cancelled")


def global_invoice_orders(start: date, end: date) -> QuerySet[Order]:
    """Orders paid from the start of `start` to the end of `end`, store time, with no issued CFDI."""
    first = datetime.combine(start, time.min, STORE_TIMEZONE)
    after = datetime.combine(end + timedelta(days=1), time.min, STORE_TIMEZONE)
    method = (
        Payment.objects.filter(order=OuterRef("pk"))
        .exclude(status__in=_UNSETTLED)
        .order_by("-id")
        .values("method")[:1]
    )
    return (
        Order.objects.filter(paid_at__gte=first, paid_at__lt=after)
        .exclude(state__in=("cancelled", "expired"))
        .exclude(invoice_request__status=InvoiceRequest.Status.ISSUED)
        .annotate(payment_method=Subquery(method))
        .order_by("paid_at", "pk")
    )


def write_global_invoice_csv(out: TextIO, start: date, end: date) -> int:
    """Write the header and one row per order to `out`; returns the number of orders."""
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(COLUMNS)
    count = 0
    for order in global_invoice_orders(start, end).iterator():
        assert order.paid_at is not None
        writer.writerow(
            (
                order.number,
                order.paid_at.astimezone(STORE_TIMEZONE).isoformat(timespec="seconds"),
                order.payment_method or "",  # type: ignore[attr-defined]
                order.total_cents,
                order.tax_included_cents,
            )
        )
        count += 1
    return count
