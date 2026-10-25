"""Facets of the public catalog (SPEC.md T5.2): the filter values a query can still choose from.

The facet keys are the `filterable_keys` of the product types in scope: the `type` filter's type
when given, otherwise the types of the products the query matches. The counts come from the
products that match every active filter, `attr.<key>` included.
"""

from typing import Any

from django.db.models import Count, QuerySet
from django.db.models.fields.json import KeyTransform

from apps.catalog.models import Product, ProductType


def scoped_types(
    products: QuerySet[Product], params: dict[str, Any]
) -> list[ProductType]:
    types = ProductType.objects.order_by("position", "id")
    if "type" in params:
        return list(types.filter(code=params["type"]))
    # Not a subquery: the search filter names the table `product`, which a subquery would alias.
    type_ids = products.order_by().values_list("product_type", flat=True).distinct()
    return list(types.filter(pk__in=list(type_ids)))


def facet_keys(types: list[ProductType]) -> list[tuple[str, str]]:
    """`(key, title)` for each filterable key, in type order, once each."""
    seen: dict[str, str] = {}
    for product_type in types:
        schema = product_type.attribute_schema
        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        keys = product_type.filterable_keys
        for key in keys if isinstance(keys, list) else []:
            if isinstance(key, str) and key not in seen:
                declared = properties.get(key, {})
                title = declared.get("title") if isinstance(declared, dict) else None
                seen[key] = title if isinstance(title, str) and title else key
    return list(seen.items())


def facet_values(products: QuerySet[Product], key: str) -> list[dict[str, Any]]:
    """The scalar values `key` takes among `products`, most common first."""
    rows = (
        products.order_by()
        .filter(attributes__has_key=key)
        .values(value=KeyTransform(key, "attributes"))
        .annotate(count=Count("pk"))
    )
    values = [
        {"value": row["value"], "count": row["count"]}
        for row in rows
        if isinstance(row["value"], str | int | float | bool)
    ]
    return sorted(values, key=lambda row: (-row["count"], str(row["value"])))


def build_facets(
    products: QuerySet[Product], params: dict[str, Any]
) -> list[dict[str, Any]]:
    return [
        {"key": key, "title": title, "values": facet_values(products, key)}
        for key, title in facet_keys(scoped_types(products, params))
    ]
