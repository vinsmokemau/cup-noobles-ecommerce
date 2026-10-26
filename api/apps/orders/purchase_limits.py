"""Purchase limits per customer (SPEC.md T8.8, REQ-061, G31, ADR-0030).

With guest checkout a customer has no account, so "the same customer" is any earlier order that
shares the email, the phone or the shipping address with the new one. A variant's units in
`pending_payment` and paid-or-later orders created within `PURCHASE_LIMIT_WINDOW_DAYS` count
toward its `purchase_limit`. The limit values and the window length are D15.
"""

import re
import unicodedata
from collections import defaultdict
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from apps.orders.models import OrderLine

# `draft` has not reserved anything yet, and `cancelled`, `expired` and `refunded` gave the
# units back.
COUNTED_STATES = (
    "pending_payment",
    "paid",
    "awaiting_stock",
    "preparing",
    "ready_for_pickup",
    "shipped",
    "delivered",
    "picked_up",
    "completed",
    "partially_refunded",
)

# A Mexican number is 10 digits; a country code or a leading 1 before them is not part of it.
PHONE_SIGNIFICANT_DIGITS = 10


def normalise_email(email: str) -> str:
    return email.strip().casefold()


def normalise_phone(phone: str) -> str:
    """The last 10 digits, so `+52 55 5555 5555` and `5555555555` match. Empty if no digits."""
    digits = re.sub(r"\D", "", phone or "")
    return digits[-PHONE_SIGNIFICANT_DIGITS:]


def _fold(text: Any) -> str:
    """Lower case, no accents, only letters and digits: `Calle  Ñandú #1` == `calle nandu 1`."""
    decomposed = unicodedata.normalize("NFKD", str(text or "")).casefold()
    return re.sub(r"[^a-z0-9]", "", decomposed)


def normalise_address(address: dict[str, Any] | None) -> str:
    """Street, numbers and postal code, folded. Empty when the street or the postal code is
    missing, so two incomplete addresses never match each other. The recipient's name is left out
    on purpose: the same door under another name is the same customer."""
    if not address:
        return ""
    street = _fold(address.get("street"))
    postal_code = _fold(address.get("postal_code"))
    if not street or not postal_code:
        return ""
    numbers = _fold(address.get("ext_number")) + "/" + _fold(address.get("int_number"))
    return f"{street}|{numbers}|{postal_code}"


def units_already_bought(
    variant_ids: list[int], *, email: str, phone: str, shipping_address: dict | None
) -> dict[int, int]:
    """Units per variant in counted orders of the window that match `email`, `phone` or the
    address. Call it with the stock rows locked: a concurrent checkout of the same customer then
    waits and sees this order once it commits."""
    if not variant_ids:
        return {}
    days = settings.PURCHASE_LIMIT_WINDOW_DAYS
    if days is None:
        raise ImproperlyConfigured(
            "PURCHASE_LIMIT_WINDOW_DAYS must be set while a variant carries a purchase limit (D15)."
        )
    wanted = (
        normalise_email(email),
        normalise_phone(phone),
        normalise_address(shipping_address),
    )
    since = timezone.now() - timedelta(days=days)
    rows = OrderLine.objects.filter(
        variant_id__in=variant_ids,
        order__state__in=COUNTED_STATES,
        order__created_at__gte=since,
    ).values_list(
        "variant_id",
        "quantity",
        "order__email",
        "order__phone",
        "order__shipping_address",
    )
    bought: dict[int, int] = defaultdict(int)
    for variant_id, quantity, order_email, order_phone, order_address in rows:
        found = (
            normalise_email(order_email),
            normalise_phone(order_phone),
            normalise_address(order_address),
        )
        if any(
            mine and mine == theirs for mine, theirs in zip(wanted, found, strict=True)
        ):
            bought[variant_id] += quantity
    return dict(bought)
