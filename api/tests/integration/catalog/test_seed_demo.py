import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from apps.catalog.models import Product, ProductType, Variant
from apps.catalog.seeds import LAUNCH_PRODUCT_TYPES

pytestmark = pytest.mark.django_db


def test_seed_demo_makes_one_published_product_per_launch_type():
    call_command("seed_demo")

    codes = {spec["code"] for spec in LAUNCH_PRODUCT_TYPES}
    products = Product.objects.select_related("product_type")
    assert {p.product_type.code for p in products} == codes
    assert products.count() == len(codes)
    assert all(p.name.startswith("[DEMO]") for p in products)
    assert all(p.status == "active" and p.published_at for p in products)
    sudadera = Product.objects.get(product_type__code="apparel")
    assert sudadera.variants.count() == 6
    assert ProductType.objects.count() == len(codes)


def test_seed_demo_twice_changes_nothing():
    call_command("seed_demo")
    before = (Product.objects.count(), Variant.objects.count())

    call_command("seed_demo")

    assert (Product.objects.count(), Variant.objects.count()) == before


def test_seed_demo_refuses_without_dev_tools():
    with override_settings(DEV_TOOLS_ENABLED=False):
        with pytest.raises(CommandError):
            call_command("seed_demo")
    assert not Product.objects.exists()
