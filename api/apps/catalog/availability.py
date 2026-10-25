"""Public availability of a variant (SPEC.md T5.3, D10 stand-in in §2.5).

The storefront sees a status, never a count. `available` follows CR-04 per stock row
(`on_hand - reserved - safety_stock`, never negative) and is summed over the active fulfillment
locations. Pre-order and pickup availability are Release 2 (T5.8).
"""

from django.db.models import (
    F,
    IntegerField,
    OuterRef,
    QuerySet,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce, Greatest

from apps.catalog.models import Variant
from apps.inventory.models import StockItem

IN_STOCK = "in_stock"
LOW_STOCK = "low_stock"
OUT_OF_STOCK = "out_of_stock"

# 5.3: `low_stock` when 1 <= available <= 5. ADR-0037.
LOW_STOCK_MAX = 5

ANNOTATION = "available_units"


def status_for(available: int) -> str:
    if available <= 0:
        return OUT_OF_STOCK
    if available <= LOW_STOCK_MAX:
        return LOW_STOCK
    return IN_STOCK


def with_available_units(queryset: QuerySet[Variant]) -> QuerySet[Variant]:
    """Annotate each variant with `available_units`, so a list needs no query per row."""
    per_variant = (
        StockItem.objects.filter(
            variant=OuterRef("pk"),
            location__is_active=True,
            location__is_fulfillment_source=True,
        )
        .order_by()
        .values("variant")
        .annotate(
            total=Sum(
                Greatest(
                    F("on_hand") - F("reserved") - F("safety_stock"),
                    Value(0),
                )
            )
        )
        .values("total")
    )
    return queryset.annotate(
        **{ANNOTATION: Coalesce(Subquery(per_variant), 0, output_field=IntegerField())}
    )


def available_units(variant: Variant) -> int:
    annotated = getattr(variant, ANNOTATION, None)
    if annotated is not None:
        return annotated
    return with_available_units(Variant.objects.filter(pk=variant.pk)).values_list(
        ANNOTATION, flat=True
    )[0]


def availability(variant: Variant) -> dict[str, str]:
    return {"status": status_for(available_units(variant))}
