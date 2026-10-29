"""The reporting exports: orders, order lines and shipments (SPEC.md T10.16, REQ-063, A19, G33).

The owner builds the weekly dashboard and the monthly report from these files outside the store;
the store adds no reporting screens. A range is two calendar dates in the store timezone (G5),
both included. Orders and their lines are in range by `placed_at`, shipments by `shipped_at`, and
each file carries every timestamp the counts need, so the owner can slice it another way.
Money is integer centavos (CR-01). A missing value is an empty cell, never a zero.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator
from datetime import date, datetime, time, timedelta
from typing import Any, TextIO

from django.db.models import OuterRef, QuerySet, Subquery

from apps.orders.models import Order, OrderLine, Shipment
from apps.orders.numbering import STORE_TIMEZONE
from apps.payments.models import Payment

ORDER_COLUMNS = (
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
)

LINE_COLUMNS = (
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
)

SHIPMENT_COLUMNS = (
    "order_number",
    "order_state",
    "paid_at",
    "carrier",
    "tracking_number",
    "cost_cents",
    "shipped_at",
    "delivered_at",
)

# A payment that never settled is not the one the customer paid with.
_UNSETTLED = ("initiated", "pending", "rejected", "cancelled")

# A spreadsheet runs a cell that starts with one of these as a formula.
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def _bounds(start: date, end: date) -> tuple[datetime, datetime]:
    first = datetime.combine(start, time.min, STORE_TIMEZONE)
    after = datetime.combine(end + timedelta(days=1), time.min, STORE_TIMEZONE)
    return first, after


def _moment(value: datetime | None) -> str:
    return (
        value.astimezone(STORE_TIMEZONE).isoformat(timespec="seconds") if value else ""
    )


def _text(value: str) -> str:
    return "'" + value if value.startswith(_FORMULA_START) else value


def _number(value: int | None) -> int | str:
    return "" if value is None else value


def order_rows(start: date, end: date) -> QuerySet[Order]:
    first, after = _bounds(start, end)
    method = (
        Payment.objects.filter(order=OuterRef("pk"))
        .exclude(status__in=_UNSETTLED)
        .order_by("-id")
        .values("method")[:1]
    )
    return (
        Order.objects.filter(placed_at__gte=first, placed_at__lt=after)
        .annotate(payment_method=Subquery(method))
        .order_by("placed_at", "pk")
    )


def line_rows(start: date, end: date) -> QuerySet[OrderLine]:
    first, after = _bounds(start, end)
    return (
        OrderLine.objects.filter(
            order__placed_at__gte=first, order__placed_at__lt=after
        )
        .select_related("order")
        .order_by("order__placed_at", "order_id", "pk")
    )


def shipment_rows(start: date, end: date) -> QuerySet[Shipment]:
    first, after = _bounds(start, end)
    return (
        Shipment.objects.filter(shipped_at__gte=first, shipped_at__lt=after)
        .select_related("order")
        .order_by("shipped_at", "pk")
    )


def _order_cells(order: Order) -> tuple[Any, ...]:
    return (
        order.number,
        order.state,
        order.fulfillment_method,
        order.payment_method or "",  # type: ignore[attr-defined]
        _moment(order.placed_at),
        _moment(order.paid_at),
        _moment(order.shipped_at),
        _moment(order.completed_at),
        _moment(order.cancelled_at),
        _text(order.cancel_reason),
        order.subtotal_cents,
        order.shipping_cents,
        order.discount_cents,
        order.total_cents,
        order.tax_included_cents,
    )


def _line_cells(line: OrderLine) -> tuple[Any, ...]:
    return (
        line.order.number,
        line.order.state,
        _moment(line.order.placed_at),
        _text(line.sku),
        _text(line.product_name),
        line.quantity,
        line.unit_price_cents,
        line.line_total_cents,
        _number(line.unit_cost_cents),
        "true" if line.is_preorder else "false",
    )


def _shipment_cells(shipment: Shipment) -> tuple[Any, ...]:
    return (
        shipment.order.number,
        shipment.order.state,
        _moment(shipment.order.paid_at),
        _text(shipment.carrier),
        _text(shipment.tracking_number),
        _number(shipment.cost_cents),
        _moment(shipment.shipped_at),
        _moment(shipment.delivered_at),
    )


def _write(
    out: TextIO, columns: tuple[str, ...], rows: Iterable[Any], cells: Any
) -> int:
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(columns)
    count = 0
    for row in rows:
        writer.writerow(cells(row))
        count += 1
    return count


def write_orders_csv(out: TextIO, start: date, end: date) -> int:
    return _write(out, ORDER_COLUMNS, order_rows(start, end).iterator(), _order_cells)


def write_lines_csv(out: TextIO, start: date, end: date) -> int:
    return _write(out, LINE_COLUMNS, line_rows(start, end).iterator(), _line_cells)


def write_shipments_csv(out: TextIO, start: date, end: date) -> int:
    return _write(
        out, SHIPMENT_COLUMNS, shipment_rows(start, end).iterator(), _shipment_cells
    )


REPORTS = {
    "orders": ("Pedidos", write_orders_csv),
    "lines": ("Líneas de pedido", write_lines_csv),
    "shipments": ("Envíos", write_shipments_csv),
}


def report_choices() -> Iterator[tuple[str, str]]:
    for key, (label, _) in REPORTS.items():
        yield key, label
