"""Catalog services (SPEC.md §4.4, T3.1): pure functions, no HTTP.

The admin, the importer and the seed call these, so every path validates attributes, generates
slugs and checks variant options the same way. Failures are `ValidationError`, never a database
error: a duplicate option set is caught here before the unique index would raise.
"""

from collections.abc import Iterable, Mapping
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Category, Product, ProductType, Variant

INVALID_OPTIONS_CODE = "invalid_options"
DUPLICATE_OPTIONS_CODE = "duplicate_options"
UNKNOWN_TYPE_CODE = "unknown_product_type"


def resolve_variant_axes(product: Product) -> list[str]:
    """`product.variant_axes` if set, else the product type's."""
    axes = (
        product.variant_axes
        if product.variant_axes is not None
        else product.product_type.variant_axes
    )
    return list(axes)


@transaction.atomic
def create_product(
    type_code: str,
    name: str,
    attributes: Mapping[str, Any] | None = None,
    *,
    categories: Iterable[Category] = (),
    **fields: Any,
) -> Product:
    """Create a draft product. `Product.save()` validates `attributes` and generates the slug.

    `fields` are other `Product` columns (`brand`, `franchise`, `subtitle`, `slug`, …).
    """
    try:
        product_type = ProductType.objects.get(code=type_code)
    except ProductType.DoesNotExist:
        raise ValidationError(
            {
                "product_type": ValidationError(
                    "Unknown product type %(code)s.",
                    code=UNKNOWN_TYPE_CODE,
                    params={"code": type_code},
                )
            }
        ) from None
    product = Product(
        product_type=product_type,
        name=name,
        attributes=dict(attributes or {}),
        **fields,
    )
    product.save()
    product.categories.add(*categories)
    return product


@transaction.atomic
def add_variant(
    product: Product,
    options: Mapping[str, Any],
    price_cents: int,
    sku: str,
    **fields: Any,
) -> Variant:
    """Add a variant whose option keys are exactly the product's resolved `variant_axes`.

    A product with no axes takes `{}`. Two variants of one product cannot share options.
    """
    options = dict(options)
    axes = resolve_variant_axes(product)
    if set(options) != set(axes):
        raise ValidationError(
            {
                "options": ValidationError(
                    "Options must have exactly the keys %(axes)s; got %(keys)s.",
                    code=INVALID_OPTIONS_CODE,
                    params={"axes": sorted(axes), "keys": sorted(options)},
                )
            }
        )
    if product.variants.filter(options=options).exists():
        raise ValidationError(
            {
                "options": ValidationError(
                    "This product already has a variant with these options.",
                    code=DUPLICATE_OPTIONS_CODE,
                )
            }
        )
    variant = Variant(
        product=product, options=options, price_cents=price_cents, sku=sku, **fields
    )
    variant.save()
    return variant


def publish_product(product: Product) -> Product:
    """Make the product `active`. `published_at` is set once and kept, so the slug stays frozen."""
    if product.published_at is None:
        product.published_at = timezone.now()
    product.status = Product.Status.ACTIVE
    product.save(update_fields=["status", "published_at", "updated_at"])
    return product


def archive_product(product: Product) -> Product:
    """Retire the product. The slug and `published_at` are kept, so old links stay reserved."""
    product.status = Product.Status.ARCHIVED
    product.save(update_fields=["status", "updated_at"])
    return product
