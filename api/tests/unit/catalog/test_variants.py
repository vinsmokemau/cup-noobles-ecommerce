import pytest
from django.core.exceptions import ValidationError

from apps.catalog.services import add_variant, create_product, resolve_variant_axes
from tests.factories.catalog import ProductFactory, ProductTypeFactory

pytestmark = pytest.mark.django_db


def test_p3_v07_options_must_match_axes():
    product_type = ProductTypeFactory(variant_axes=["talla", "color"])
    product = ProductFactory(product_type=product_type)

    variant = add_variant(product, {"talla": "S", "color": "negro"}, 59900, "HOO-S-N")
    assert variant.options == {"talla": "S", "color": "negro"}

    for bad in (
        {"talla": "S"},
        {"talla": "S", "color": "negro", "corte": "x"},
        {"talla": "S", "tono": "negro"},
        {},
    ):
        with pytest.raises(ValidationError) as rejected:
            add_variant(product, bad, 59900, "HOO-BAD")
        assert rejected.value.error_dict["options"][0].code == "invalid_options"

    # product.variant_axes overrides the type default
    product.variant_axes = ["talla"]
    assert resolve_variant_axes(product) == ["talla"]
    assert add_variant(product, {"talla": "M"}, 59900, "HOO-M").options == {
        "talla": "M"
    }
    with pytest.raises(ValidationError):
        add_variant(product, {"talla": "L", "color": "negro"}, 59900, "HOO-L-N")


def test_axes_fall_back_to_the_type_and_an_empty_list_is_not_unset():
    product = ProductFactory(product_type=ProductTypeFactory(variant_axes=["talla"]))
    assert resolve_variant_axes(product) == ["talla"]

    product.variant_axes = []
    assert resolve_variant_axes(product) == []
    assert add_variant(product, {}, 100, "SINGLE").options == {}


def test_duplicate_options_raise_validation_error():
    product = ProductFactory(product_type=ProductTypeFactory(variant_axes=["talla"]))
    add_variant(product, {"talla": "S"}, 100, "A")

    with pytest.raises(ValidationError) as duplicate:
        add_variant(product, {"talla": "S"}, 100, "B")
    assert duplicate.value.error_dict["options"][0].code == "duplicate_options"


def test_create_product_validates_attributes_and_generates_slug():
    ProductTypeFactory(
        code="figura",
        attribute_schema={
            "type": "object",
            "required": ["numero"],
            "properties": {"numero": {"type": "integer"}},
        },
    )

    first = create_product("figura", "Pikachu", {"numero": 25})
    second = create_product("figura", "Pikachu", {"numero": 26})
    assert (first.slug, second.slug) == ("pikachu", "pikachu-2")
    assert first.status == "draft"

    with pytest.raises(ValidationError) as missing:
        create_product("figura", "Sin número", {})
    assert "attributes" in missing.value.error_dict

    with pytest.raises(ValidationError) as unknown:
        create_product("nope", "X", {})
    assert unknown.value.error_dict["product_type"][0].code == "unknown_product_type"
