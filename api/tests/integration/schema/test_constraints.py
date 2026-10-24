"""Database constraints, exercised below the ORM's own validation (SPEC.md Phase 2 Verify)."""

import datetime

import pytest
from django.db import IntegrityError, transaction

from tests.factories.catalog import (
    CategoryFactory,
    ProductFactory,
    ProductTypeFactory,
    VariantFactory,
)

pytestmark = pytest.mark.django_db


def rejected(constraint: str):
    """The block must raise IntegrityError naming `constraint`; the transaction survives it."""
    return _Rejected(constraint)


class _Rejected:
    def __init__(self, constraint: str) -> None:
        self._raises = pytest.raises(IntegrityError, match=constraint)
        self._savepoint = transaction.atomic()

    def __enter__(self) -> None:
        self._raises.__enter__()
        self._savepoint.__enter__()

    def __exit__(self, *exc) -> bool:
        self._savepoint.__exit__(*exc)
        return self._raises.__exit__(*exc)


def test_p2_v03_duplicate_variant_options():
    product = ProductFactory()
    VariantFactory(product=product, options={"talla": "L", "color": "negro"})
    with rejected("variant_product_options_uq"):
        VariantFactory(product=product, options={"talla": "L", "color": "negro"})
    # jsonb normalises key order, so the same keys in another order are the same options.
    with rejected("variant_product_options_uq"):
        VariantFactory(product=product, options={"color": "negro", "talla": "L"})
    VariantFactory(product=product, options={"talla": "M", "color": "negro"})
    VariantFactory(options={"talla": "L", "color": "negro"})  # another product


def test_p2_v08_preorder_constraints():
    release = datetime.date(2027, 3, 1)
    with rejected("variant_preorder_needs_date"):
        VariantFactory(is_preorder=True)
    with rejected("variant_preorder_within_limit"):
        VariantFactory(
            is_preorder=True,
            expected_release_date=release,
            preorder_limit=10,
            preorder_committed=11,
        )
    VariantFactory(
        is_preorder=True,
        expected_release_date=release,
        preorder_limit=10,
        preorder_committed=10,
    )


def test_p2_v12_catalog_constraints(raw_sql):
    with rejected("product_active_needs_publish"):
        ProductFactory(status="active", published_at=None)

    category = CategoryFactory()
    with rejected("category_not_self_parent"):
        raw_sql("UPDATE category SET parent_id = id WHERE id = %s", [category.id])

    product_type = ProductTypeFactory()
    insert_product = (
        "INSERT INTO product (product_type_id, slug, name, attributes) "
        "VALUES (%s, %s, 'Producto', %s::jsonb)"
    )
    with rejected("product_attributes_is_object"):
        raw_sql(insert_product, [product_type.id, "attrs-array", "[]"])
    with rejected("product_attributes_is_object"):
        raw_sql(insert_product, [product_type.id, "attrs-scalar", '"texto"'])
    raw_sql(insert_product, [product_type.id, "attrs-object", "{}"])

    product = ProductFactory()
    insert_variant = (
        "INSERT INTO variant (product_id, sku, price_cents, options) "
        "VALUES (%s, %s, 100, %s::jsonb)"
    )
    with rejected("variant_options_is_object"):
        raw_sql(insert_variant, [product.id, "OPT-ARRAY", '["L"]'])
    raw_sql(insert_variant, [product.id, "OPT-OBJECT", "{}"])
