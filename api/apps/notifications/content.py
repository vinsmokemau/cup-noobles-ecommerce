"""The R1 email templates (SPEC.md §4.5, T11.3): a subject and the values of the layout's slots.

Each template is a function from the outbox context and the order to `EmailContent`. The layout
is the vendored DS reference (`rendering.py`), so nothing here is visual: components hold no copy
of their own (CR-32), and the copy below is es-MX in the DS voice (tú, specific, no exclamation
marks). Every value comes from the order or the outbox context; none is a business value.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from django.conf import settings

from apps.notifications.formatting import format_deadline, format_mxn
from apps.orders.models import Order

BRAND = "Cup Noobles"
LOGO_PATH = "/email/logo-horizontal.png"


class UnknownTemplate(Exception):
    """No template is registered under this name."""


@dataclass(frozen=True)
class Item:
    name: str
    quantity: str
    amount: str


@dataclass(frozen=True)
class Total:
    label: str
    amount: str


@dataclass(frozen=True)
class EmailContent:
    """What a template decides: the subject and the layout's 18 slots. `items` and `totals` fill
    the repeated rows of the card; `slots` holds the other fifteen."""

    subject: str
    slots: dict[str, str]
    items: tuple[Item, ...] = field(default=())
    totals: tuple[Total, ...] = field(default=())


def _site(path: str = "/") -> str:
    return f"{str(settings.SITE_URL).rstrip('/')}{path}"


def _items(order: Order) -> tuple[Item, ...]:
    items = []
    for line in order.lines.order_by("id"):
        name = line.product_name
        if line.options_snapshot:
            options = ", ".join(str(value) for value in line.options_snapshot.values())
            name = f"{name} ({options})"
        items.append(Item(name, f"x{line.quantity}", format_mxn(line.line_total_cents)))
    return tuple(items)


def _order_totals(order: Order) -> tuple[Total, ...]:
    return (
        Total("Subtotal", format_mxn(order.subtotal_cents)),
        Total("Envío", format_mxn(order.shipping_cents)),
        Total("Total", format_mxn(order.total_cents)),
    )


def _layout(
    *,
    subject: str,
    heading: str,
    body: str,
    card_title: str,
    card_body: str,
    card_footer: str,
    button_label: str,
    button_url: str,
    items: tuple[Item, ...],
    totals: tuple[Total, ...],
) -> EmailContent:
    return EmailContent(
        subject=subject,
        slots={
            "home_url": _site(),
            "logo_url": _site(LOGO_PATH),
            "logo_alt": BRAND,
            "heading": heading,
            "body": body,
            "card_title": card_title,
            "card_body": card_body,
            "card_footer": card_footer,
            "button_url": button_url,
            "button_label": button_label,
            "footer_text": f"Recibiste este correo porque hiciste un pedido en {BRAND}.",
            "footer_link_url": _site("/legal/privacidad"),
            "footer_link_label": "Aviso de privacidad",
        },
        items=items,
        totals=totals,
    )


def _need_order(template: str, order: Order | None) -> Order:
    if order is None:
        raise ValueError(f"The {template} email needs its order")
    return order


def _track_button() -> dict[str, str]:
    return {"button_label": "Consultar mi pedido", "button_url": _site("/rastrear")}


def _order_confirmation(context: dict[str, Any], order: Order | None) -> EmailContent:
    order = _need_order("order_confirmation", order)
    return _layout(
        subject=f"Pago confirmado: pedido {order.number}",
        heading="Tu pedido está confirmado",
        body="Recibimos tu pago. Estamos preparando tu pedido y te avisaremos cuando salga de nuestro almacén.",
        card_title=f"Pedido {order.number}",
        card_body="Esto es lo que compraste.",
        card_footer="Si algo no es correcto, responde a este correo.",
        items=_items(order),
        totals=_order_totals(order),
        **_track_button(),
    )


def _oxxo_voucher(context: dict[str, Any], order: Order | None) -> EmailContent:
    order = _need_order("oxxo_voucher", order)
    expires = context.get("voucher_expires_at")
    if expires:
        due = format_deadline(datetime.fromisoformat(expires))
        card_body = f"Paga en OXXO antes del {due}."
    else:
        card_body = "Abre tu ficha para ver hasta cuándo puedes pagar."
    return _layout(
        subject=f"Tu ficha de pago en OXXO: pedido {order.number}",
        heading="Tu ficha de pago está lista",
        body="Paga en una tienda OXXO con tu ficha. Confirmamos tu pedido en cuanto recibimos el pago.",
        card_title=f"Pedido {order.number}",
        card_body=card_body,
        card_footer="Si pasa la fecha límite, el pedido vence y la ficha deja de servir.",
        button_label="Ver mi ficha de pago",
        button_url=str(context["voucher_url"]),
        items=_items(order),
        totals=_order_totals(order),
    )


def _order_expired(context: dict[str, Any], order: Order | None) -> EmailContent:
    order = _need_order("order_expired", order)
    return _layout(
        subject=f"Tu pedido {order.number} venció",
        heading="Tu pedido venció",
        body="No recibimos el pago a tiempo, así que liberamos los artículos de tu pedido. No se hizo ningún cargo.",
        card_title=f"Pedido {order.number}",
        card_body="Estos eran los artículos.",
        card_footer="Si todavía los quieres, haz un pedido nuevo en nuestro sitio.",
        button_label="Ir a Cup Noobles",
        button_url=_site(),
        items=_items(order),
        totals=_order_totals(order),
    )


def _order_shipped(context: dict[str, Any], order: Order | None) -> EmailContent:
    order = _need_order("order_shipped", order)
    tracking_url = context.get("tracking_url") or ""
    button = (
        {"button_label": "Rastrear mi envío", "button_url": str(tracking_url)}
        if tracking_url
        else _track_button()
    )
    return _layout(
        subject=f"Tu pedido {order.number} va en camino",
        heading="Tu pedido está en camino",
        body="Tu pedido ya salió de nuestro almacén.",
        card_title=f"Pedido {order.number}",
        card_body=f"Número de guía: {context['tracking_number']}.",
        card_footer="Si algo no es correcto, responde a este correo.",
        items=_items(order),
        totals=_order_totals(order),
        **button,
    )


def _order_cancelled(context: dict[str, Any], order: Order | None) -> EmailContent:
    order = _need_order("order_cancelled", order)
    refunded = int(context.get("refunded_cents") or 0)
    if refunded > 0:
        body = f"Cancelamos tu pedido y pedimos el reembolso de {format_mxn(refunded)} a tu medio de pago."
    else:
        body = "Cancelamos tu pedido. No se hizo ningún cargo."
    return _layout(
        subject=f"Cancelamos tu pedido {order.number}",
        heading="Tu pedido se canceló",
        body=body,
        card_title=f"Pedido {order.number}",
        card_body="Estos eran los artículos.",
        card_footer="Si tienes dudas, responde a este correo.",
        items=_items(order),
        totals=_order_totals(order),
        **_track_button(),
    )


def _refund_issued(context: dict[str, Any], order: Order | None) -> EmailContent:
    order = _need_order("refund_issued", order)
    refund = int(context["refund_cents"])
    refunded_total = int(context["refunded_total_cents"])
    return _layout(
        subject=f"Reembolso de tu pedido {order.number}",
        heading="Confirmamos tu reembolso",
        body=f"Reembolsamos {format_mxn(refund)} de tu pedido.",
        card_title=f"Pedido {order.number}",
        card_body="Esto es lo que incluía el pedido.",
        card_footer="Si tienes dudas, responde a este correo.",
        items=_items(order),
        totals=(
            Total("Total pagado", format_mxn(order.total_cents)),
            Total("Reembolsado", format_mxn(refunded_total)),
        ),
        **_track_button(),
    )


def _cfdi_issued(context: dict[str, Any], order: Order | None) -> EmailContent:
    order = _need_order("cfdi_issued", order)
    return _layout(
        subject=f"Tu factura del pedido {order.number}",
        heading="Tu factura está lista",
        body="Adjuntamos el PDF y el XML de tu factura (CFDI).",
        card_title=f"Pedido {order.number}",
        card_body=f"Folio: {context['folio']}.",
        card_footer="Si algún dato no es correcto, responde a este correo.",
        items=_items(order),
        totals=_order_totals(order),
        **_track_button(),
    )


TEMPLATES: dict[str, Callable[[dict[str, Any], Order | None], EmailContent]] = {
    "order_confirmation": _order_confirmation,
    "oxxo_voucher": _oxxo_voucher,
    "order_expired": _order_expired,
    "order_shipped": _order_shipped,
    "order_cancelled": _order_cancelled,
    "refund_issued": _refund_issued,
    "cfdi_issued": _cfdi_issued,
}


def build_content(
    template: str, context: dict[str, Any], order: Order | None
) -> EmailContent:
    """The subject and slot values of `template`. Raises `UnknownTemplate`."""
    try:
        builder = TEMPLATES[template]
    except KeyError:
        raise UnknownTemplate(template) from None
    return builder(context, order)
