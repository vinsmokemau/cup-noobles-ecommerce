"""Query parameters of the public product list (SPEC.md T5.1).

The dynamic `attr.<key>` filters are T5.2; the `preorder` filter is R2 (T5.8).
"""

from typing import Any

from django.db.models import Exists, OuterRef, QuerySet
from rest_framework import serializers

from apps.catalog import search
from apps.catalog.availability import ANNOTATION, with_available_units
from apps.catalog.models import Category, Product, ProductCategory, Variant


class ProductQuerySerializer(serializers.Serializer):
    category = serializers.CharField(
        required=False,
        max_length=200,
        help_text="Category slug; includes its descendants.",
    )
    franchise = serializers.CharField(required=False, max_length=200)
    brand = serializers.CharField(required=False, max_length=200)
    type = serializers.CharField(
        required=False, max_length=200, help_text="Product type code."
    )
    q = serializers.CharField(required=False, max_length=100)
    min_price = serializers.IntegerField(
        required=False, min_value=0, help_text="Centavos of MXN, IVA included."
    )
    max_price = serializers.IntegerField(
        required=False, min_value=0, help_text="Centavos of MXN, IVA included."
    )
    in_stock = serializers.BooleanField(
        required=False, help_text="`true` keeps products with a unit available."
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        low, high = attrs.get("min_price"), attrs.get("max_price")
        if low is not None and high is not None and low > high:
            raise serializers.ValidationError(
                {"min_price": ["No puede ser mayor que max_price."]}
            )
        return attrs


def category_ids(slug: str) -> list[int]:
    """The active category with this slug and every active descendant; empty if none."""
    rows = list(
        Category.objects.filter(is_active=True).values_list("id", "slug", "parent_id")
    )
    start = next(
        (pk for pk, row_slug, _ in rows if row_slug.lower() == slug.lower()), None
    )
    if start is None:
        return []
    found, frontier = [start], [start]
    while frontier:
        frontier = [
            pk for pk, _, parent in rows if parent in frontier and pk not in found
        ]
        found.extend(frontier)
    return found


def active_variants() -> QuerySet[Variant]:
    return Variant.objects.filter(product=OuterRef("pk"), is_active=True)


def filter_products(
    queryset: QuerySet[Product], params: dict[str, Any]
) -> QuerySet[Product]:
    if "category" in params:
        queryset = queryset.filter(
            Exists(
                ProductCategory.objects.filter(
                    product=OuterRef("pk"),
                    category__in=category_ids(params["category"]),
                )
            )
        )
    if "franchise" in params:
        queryset = queryset.filter(franchise__slug=params["franchise"])
    if "brand" in params:
        queryset = queryset.filter(brand__slug=params["brand"])
    if "type" in params:
        queryset = queryset.filter(product_type__code=params["type"])

    variants = active_variants()
    priced = "min_price" in params or "max_price" in params
    if "min_price" in params:
        variants = variants.filter(price_cents__gte=params["min_price"])
    if "max_price" in params:
        variants = variants.filter(price_cents__lte=params["max_price"])
    if priced:
        queryset = queryset.filter(Exists(variants))

    if params.get("in_stock"):
        stocked = with_available_units(active_variants()).filter(
            **{f"{ANNOTATION}__gt": 0}
        )
        queryset = queryset.filter(Exists(stocked))

    if params.get("q"):
        queryset = search.matching(queryset, params["q"])
    return queryset
