"""Find the Part A stand-ins that must be gone before production (SPEC.md §2.5, REQ-065).

Each finder returns human-readable findings; an empty list means none of that kind remains.
T15.8 adds the `[DEMO]` marker.
"""

import json
from pathlib import Path

from django.conf import settings

from apps.catalog.models import ProductType
from apps.inventory.models import Location
from apps.shipping.models import ShippingRate, ShippingZone

MARKER = "[PLACEHOLDER]"
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


def find_placeholders() -> list[str]:
    return (
        placeholder_names()
        + placeholder_schemas()
        + placeholder_cfdi_catalog()
        + dev_default_settings()
    )
