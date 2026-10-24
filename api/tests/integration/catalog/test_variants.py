import itertools
import json

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.catalog.models import Variant
from apps.catalog.services import add_variant
from tests.factories.catalog import ProductFactory, ProductTypeFactory

pytestmark = pytest.mark.django_db

SIZES = ("S", "M", "L")
COLORS = ("negro", "blanco")


def test_p3_v01_apparel_six_variants_seventh_rejected(admin_client):
    product_type = ProductTypeFactory(variant_axes=["talla", "color"])
    product = ProductFactory(product_type=product_type)

    for size, color in itertools.product(SIZES, COLORS):
        add_variant(
            product, {"talla": size, "color": color}, 59900, f"HOO-{size}-{color}"
        )
    assert product.variants.count() == 6

    with pytest.raises(ValidationError) as rejected:
        add_variant(product, {"talla": "S", "color": "negro"}, 59900, "HOO-DUP")
    assert rejected.value.error_dict["options"][0].code == "duplicate_options"
    assert product.variants.count() == 6

    # The admin inline: the same duplicate is a form error on the page, not a 500.
    variants = list(product.variants.order_by("pk"))
    data = {
        "name": product.name,
        "slug": product.slug,
        "product_type": product_type.pk,
        "subtitle": "",
        "description_md": "",
        "attributes": "{}",
        "featured_position": 0,
        "variants-TOTAL_FORMS": len(variants) + 1,
        "variants-INITIAL_FORMS": len(variants),
        "variants-MIN_NUM_FORMS": 0,
        "variants-MAX_NUM_FORMS": 1000,
        "product_image-TOTAL_FORMS": 0,
        "product_image-INITIAL_FORMS": 0,
        "product_image-MIN_NUM_FORMS": 0,
        "product_image-MAX_NUM_FORMS": 1000,
    }
    rows = [(v.pk, v.sku, json.dumps(v.options)) for v in variants]
    rows.append(("", "HOO-DUP", json.dumps({"talla": "S", "color": "negro"})))
    for i, (pk, sku, options) in enumerate(rows):
        data |= {
            f"variants-{i}-id": pk,
            f"variants-{i}-product": product.pk,
            f"variants-{i}-sku": sku,
            f"variants-{i}-options": options,
            f"variants-{i}-price_cents": 59900,
            f"variants-{i}-weight_grams": 0,
            f"variants-{i}-requires_shipping": "on",
            f"variants-{i}-is_active": "on",
            f"variants-{i}-position": i,
        }
    response = admin_client.post(
        reverse("admin:catalog_product_change", args=[product.pk]), data
    )

    assert response.status_code == 200
    assert "already has a variant with these options" in response.content.decode()
    assert Variant.objects.filter(product=product).count() == 6
