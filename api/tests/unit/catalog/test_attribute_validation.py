import pytest
from django.core.exceptions import ValidationError
from rest_framework.exceptions import ValidationError as DrfValidationError

from apps.catalog.models import ProductType
from apps.catalog.seeds import LAUNCH_PRODUCT_TYPES, seed_product_types
from apps.catalog.serializers import ProductWriteSerializer
from tests.factories.catalog import ProductFactory, ProductTypeFactory

pytestmark = pytest.mark.django_db

WRONG_VALUES = {"string": 123, "integer": "abc", "boolean": "si"}
NON_EMPTY_TYPES = [
    spec for spec in LAUNCH_PRODUCT_TYPES if spec["attribute_schema"]["properties"]
]


def pointers(error: ValidationError) -> list[str]:
    return [(entry.params or {})["pointer"] for entry in error.error_dict["attributes"]]


def valid_attributes(schema: dict) -> dict:
    return {
        key: {"string": "x", "integer": 1, "boolean": True}[
            schema["properties"][key]["type"]
        ]
        for key in schema.get("required", [])
    }


def test_p2_v05_error_names_json_pointer():
    seed_product_types()
    figure = ProductType.objects.get(code="figure")
    attributes = {"numero": "abc"}

    with pytest.raises(ValidationError) as saved:
        ProductFactory(product_type=figure, attributes=attributes)
    assert "/numero" in pointers(saved.value)
    assert any(
        message.startswith("/numero: ")
        for message in saved.value.message_dict["attributes"]
    )

    serializer = ProductWriteSerializer(
        data={
            "product_type": figure.pk,
            "slug": "figura",
            "name": "Figura",
            "attributes": attributes,
        }
    )
    with pytest.raises(DrfValidationError) as serialized:
        serializer.is_valid(raise_exception=True)
    assert any(
        message.startswith("/numero: ")
        for message in serialized.value.detail["attributes"]
    )


@pytest.mark.parametrize("spec", NON_EMPTY_TYPES, ids=lambda spec: spec["code"])
def test_p2_v14_schema_rules(spec):
    seed_product_types()
    product_type = ProductType.objects.get(code=spec["code"])
    schema = product_type.attribute_schema
    base = valid_attributes(schema)
    ProductFactory(
        product_type=product_type, attributes=base
    )  # the base itself is accepted

    def rejected(attributes: dict) -> list[str]:
        with pytest.raises(ValidationError) as error:
            ProductFactory(product_type=product_type, attributes=attributes)
        return pointers(error.value)

    assert rejected({**base, "clave_desconocida": "x"}) == ["/clave_desconocida"]

    required = schema["required"][0]
    assert rejected({k: v for k, v in base.items() if k != required}) == [
        f"/{required}"
    ]

    typed = next(
        key
        for key in schema["properties"]
        if schema["properties"][key]["type"] in WRONG_VALUES
    )
    wrong = WRONG_VALUES[schema["properties"][typed]["type"]]
    assert rejected({**base, typed: wrong}) == [f"/{typed}"]


def test_pointer_escapes_keys_and_reports_nested_paths():
    product_type = ProductTypeFactory(
        attribute_schema={
            "type": "object",
            "properties": {
                "a/b": {"type": "integer"},
                "medidas": {
                    "type": "object",
                    "properties": {"alto": {"type": "integer"}},
                    "required": ["alto"],
                },
            },
        }
    )
    with pytest.raises(ValidationError) as error:
        ProductFactory(
            product_type=product_type, attributes={"a/b": "x", "medidas": {}}
        )
    assert pointers(error.value) == ["/a~1b", "/medidas/alto"]


def test_non_object_attributes_report_the_root():
    product_type = ProductTypeFactory()
    product = ProductFactory.build(product_type=product_type, attributes=[])
    with pytest.raises(ValidationError) as error:
        product.clean()
    assert pointers(error.value) == ["/"]


def test_save_skips_validation_when_update_fields_exclude_attributes():
    product = ProductFactory()
    product.name = "Otro nombre"
    product.attributes = {"invalido": True}
    product.product_type.attribute_schema = {
        "type": "object",
        "additionalProperties": False,
    }
    product.save(update_fields=["name"])
    with pytest.raises(ValidationError):
        product.save(update_fields=["attributes"])


def test_serializer_partial_update_validates_against_the_instance_type():
    seed_product_types()
    figure = ProductType.objects.get(code="figure")
    product = ProductFactory(product_type=figure, attributes={"linea": "Nendoroid"})

    ok = ProductWriteSerializer(product, data={"name": "Nuevo"}, partial=True)
    assert ok.is_valid(), ok.errors

    bad = ProductWriteSerializer(
        product, data={"attributes": {"numero": "abc"}}, partial=True
    )
    assert not bad.is_valid()
    assert any(message.startswith("/numero: ") for message in bad.errors["attributes"])
