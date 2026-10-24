import pytest
from django.core.exceptions import ValidationError

from apps.catalog.services import archive_product, publish_product
from tests.factories.catalog import ProductFactory

pytestmark = pytest.mark.django_db


def test_p3_v12_publish_and_archive():
    product = ProductFactory(slug="figura")
    assert product.published_at is None

    publish_product(product)
    product.refresh_from_db()
    assert product.status == "active"
    assert product.published_at is not None
    published_at = product.published_at

    archive_product(product)
    product.refresh_from_db()
    assert product.status == "archived"
    assert product.slug == "figura"
    assert product.published_at == published_at


def test_republishing_keeps_the_first_published_at():
    product = publish_product(ProductFactory())
    first = product.published_at

    archive_product(product)
    publish_product(product)

    assert product.status == "active"
    assert product.published_at == first


def test_slug_is_frozen_once_published():
    product = publish_product(ProductFactory(slug="figura"))

    product.slug = "otra"
    with pytest.raises(ValidationError):
        product.save()
