"""Find the Part A stand-ins that must be gone before production (SPEC.md §2.5, REQ-065).

Each finder returns human-readable findings; an empty list means none of that kind remains.
The rows of the demo dataset (15.A) count too: they carry the `[DEMO]` marker (T15.8).
"""

import json
from pathlib import Path

from django.conf import settings

from apps.catalog.models import Product, ProductType
from apps.inventory.models import Location
from apps.orders.models import OrderLine
from apps.shipping.models import ShippingRate, ShippingZone

MARKER = "[PLACEHOLDER]"
# Every product name of the demo dataset starts with it (15.A).
DEMO_MARKER = "[DEMO]"
CFDI_CATALOG = Path(settings.BASE_DIR) / "fixtures" / "cfdi_catalogs.json"

# D6 and D7 dev defaults (§2.5), the values `config/settings/base.py` falls back to.
SETTING_DEV_DEFAULTS: dict[str, object] = {
    "RESERVATION_TTL_SPEI_HOURS": 4,
    "RESERVATION_TTL_OXXO_HOURS": 72,
    "PAYMENT_INSTALLMENT_OPTIONS": [3, 6],
}


def _named(kind: str, model: type) -> list[str]:
    rows = model.objects.filter(name__contains=MARKER)  # type: ignore[attr-defined]
    return [f"{kind} {row.name!r}" for row in rows.order_by("id")]


def placeholder_names() -> list[str]:
    return (
        _named("location", Location)
        + _named("shipping_zone", ShippingZone)
        + _named("shipping_rate", ShippingRate)
    )


def placeholder_schemas() -> list[str]:
    return [
        f"product_type {product_type.code!r} attribute_schema"
        for product_type in ProductType.objects.order_by("id")
        if product_type.attribute_schema.get("$comment") == MARKER
    ]


def placeholder_cfdi_catalog() -> list[str]:
    catalog = json.loads(CFDI_CATALOG.read_text(encoding="utf-8"))
    return [str(CFDI_CATALOG)] if catalog.get("$comment") == MARKER else []


def dev_default_settings() -> list[str]:
    return [
        f"setting {name}={getattr(settings, name)!r}"
        for name, default in SETTING_DEV_DEFAULTS.items()
        if getattr(settings, name) == default
    ]


def demo_rows() -> list[str]:
    """The `[DEMO]` rows: demo products, and the order lines that copied a demo product's name.

    An order line keeps the name after its product is renamed or deleted, so the orders of a
    demo dataset are found even when its products are gone.
    """
    products = Product.objects.filter(name__contains=DEMO_MARKER).order_by("id")
    lines = (
        OrderLine.objects.filter(product_name__contains=DEMO_MARKER)
        .select_related("order")
        .order_by("id")
    )
    return [f"product {product.name!r}" for product in products] + [
        f"order_line {line.product_name!r} of order {line.order.number or line.order_id}"
        for line in lines
    ]


def find_placeholders() -> list[str]:
    return (
        placeholder_names()
        + placeholder_schemas()
        + placeholder_cfdi_catalog()
        + demo_rows()
        + dev_default_settings()
    )
