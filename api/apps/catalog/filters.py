"""Query parameters of the public product list (SPEC.md T5.1) and its `attr.<key>` filters (T5.2).

The `preorder` filter is R2 (T5.8).

An `attr.<key>` filter is allowed only when `<key>` is in the `filterable_keys` of a product type
in scope: the `type` filter's type when given, otherwise any type. The key is checked against that
list before the query is built, and it reaches the database as a bound parameter (`@>`), never
as SQL text.
"""

from collections.abc import Mapping
from typing import Any

from django.db.models import Exists, OuterRef, Q, QuerySet
from rest_framework import serializers

from apps.catalog import search
from apps.catalog.availability import ANNOTATION, with_available_units
from apps.catalog.models import (
    Category,
    Product,
    ProductCategory,
    ProductType,
    Variant,
)

ATTR_PREFIX = "attr."
ATTR_PARAM = "attr"  # where `parse_query` puts the validated attribute filters


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


def _coerce(value: str, schema_type: object) -> Any:
    """The query-string `value` as the JSON type its attribute schema declares."""
    if schema_type == "integer":
        return int(value)
    if schema_type == "number":
        return float(value)
    if schema_type == "boolean":
        lowered = value.lower()
        if lowered not in ("true", "false"):
            raise ValueError(value)
        return lowered == "true"
    return value


def attribute_filters(
    raw: Mapping[str, str], type_code: str | None
) -> dict[str, list[Any]]:
    """Validate the `attr.<key>` parameters of `raw`.

    Returns `{key: [candidate values]}`: one candidate per distinct JSON type the key has across
    the types in scope. Raises a 400 for a key no type in scope lists in `filterable_keys` and
    for a value the key's schema cannot hold.
    """
    wanted = {
        key[len(ATTR_PREFIX) :]: value
        for key, value in raw.items()
        if key.startswith(ATTR_PREFIX)
    }
    if not wanted:
        return {}

    types = ProductType.objects.all()
    if type_code is not None:
        types = types.filter(code=type_code)
    schema_types: dict[str, list[object]] = {}
    for filterable, schema in types.values_list("filterable_keys", "attribute_schema"):
        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        for key in filterable if isinstance(filterable, list) else []:
            if isinstance(key, str):
                declared = properties.get(key, {})
                schema_types.setdefault(key, []).append(
                    declared.get("type") if isinstance(declared, dict) else None
                )

    errors: dict[str, list[str]] = {}
    found: dict[str, list[Any]] = {}
    for key, value in wanted.items():
        if key not in schema_types:
            errors[ATTR_PREFIX + key] = ["Este atributo no se puede filtrar."]
            continue
        candidates: list[Any] = []
        for schema_type in schema_types[key]:
            try:
                candidate = _coerce(value, schema_type)
            except ValueError:
                continue
            if all(
                (type(candidate), candidate) != (type(other), other)
                for other in candidates
            ):
                candidates.append(candidate)
        if not candidates:
            errors[ATTR_PREFIX + key] = ["Valor no válido para este atributo."]
        else:
            found[key] = candidates
    if errors:
        raise serializers.ValidationError(errors)
    return found


def parse_query(raw: Mapping[str, str]) -> dict[str, Any]:
    """The validated filters of a catalog request: the fixed ones, plus `attr` (T5.2)."""
    query = ProductQuerySerializer(data=raw)
    query.is_valid(raise_exception=True)
    params: dict[str, Any] = dict(query.validated_data)
    attrs = attribute_filters(raw, params.get("type"))
    if attrs:
        params[ATTR_PARAM] = attrs
    return params


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

    for key, candidates in params.get(ATTR_PARAM, {}).items():
        matches = Q()
        for candidate in candidates:
            matches |= Q(attributes__contains={key: candidate})
        queryset = queryset.filter(matches)

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
