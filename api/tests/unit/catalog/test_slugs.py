import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.catalog.slugs import FALLBACK_SLUG, slugify
from tests.factories.catalog import ProductFactory

pytestmark = pytest.mark.django_db


def test_slugify_is_ascii_lowercase_and_hyphenated():
    assert slugify("Nendoroid  Pokémon: Pikachu!") == "nendoroid-pokemon-pikachu"
    assert slugify("!!!") == FALLBACK_SLUG


def test_p3_v05_slug_collision_suffix():
    products = [ProductFactory(name="Sudadera Negra", slug="") for _ in range(3)]

    assert [p.slug for p in products] == [
        "sudadera-negra",
        "sudadera-negra-2",
        "sudadera-negra-3",
    ]


def test_slug_given_explicitly_is_kept():
    assert ProductFactory(name="Sudadera Negra", slug="mi-slug").slug == "mi-slug"


def test_resaving_a_blank_slug_product_does_not_collide_with_itself():
    product = ProductFactory(name="Figura", slug="")
    product.save()

    assert product.slug == "figura"


def test_p3_v06_slug_immutable_after_publish():
    product = ProductFactory(name="Figura", slug="figura")

    product.slug = "figura-nueva"
    product.save()
    product.refresh_from_db()
    assert product.slug == "figura-nueva"

    product.published_at = timezone.now()
    product.save()

    product.slug = "otro"
    with pytest.raises(ValidationError) as changed:
        product.save()
    assert changed.value.error_dict["slug"][0].code == "slug_immutable"
    product.refresh_from_db()
    assert product.slug == "figura-nueva"

    product.slug = "figura-nueva"
    product.save()
