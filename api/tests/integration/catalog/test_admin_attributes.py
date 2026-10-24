import pytest
from django.urls import reverse

from apps.catalog.models import Product
from tests.factories.catalog import ProductFactory, ProductTypeFactory

pytestmark = pytest.mark.django_db

ADD = "admin:catalog_product_add"
CHANGE = "admin:catalog_product_change"

FIGURE_SCHEMA = {
    "type": "object",
    "properties": {
        "linea": {"type": "string", "title": "Línea"},
        "numero": {"type": "integer"},
        "escala": {"type": "string", "enum": ["1/7", "1/8"]},
        "peso": {"type": "number"},
        "edicion_limitada": {"type": "boolean"},
    },
    "required": ["numero"],
    "additionalProperties": False,
}


def product_form(product_type, **extra):
    return {
        "name": "Nendoroid Miku",
        "slug": "",
        "product_type": product_type.pk,
        "subtitle": "",
        "description_md": "",
        "featured_position": 0,
        "variants-TOTAL_FORMS": 0,
        "variants-INITIAL_FORMS": 0,
        "variants-MIN_NUM_FORMS": 0,
        "variants-MAX_NUM_FORMS": 1000,
        "images-TOTAL_FORMS": 0,
        "images-INITIAL_FORMS": 0,
        "images-MIN_NUM_FORMS": 0,
        "images-MAX_NUM_FORMS": 1000,
        **extra,
    }


def test_p3_v02_missing_required_attribute_field_error(admin_client):
    figure = ProductTypeFactory(code="figure", attribute_schema=FIGURE_SCHEMA)

    response = admin_client.post(
        reverse(ADD), product_form(figure, attr_linea="Nendoroid")
    )

    assert response.status_code == 200
    assert "attr_numero" in response.context["adminform"].form.errors
    assert not Product.objects.exists()


def test_typed_fields_are_saved_as_typed_attributes(admin_client):
    figure = ProductTypeFactory(code="figure", attribute_schema=FIGURE_SCHEMA)

    response = admin_client.post(
        reverse(ADD),
        product_form(
            figure,
            attr_linea="Nendoroid",
            attr_numero="1234",
            attr_escala="1/7",
            attr_peso="0.5",
            attr_edicion_limitada="on",
        ),
    )

    assert response.status_code == 302, response.context["errors"]
    assert Product.objects.get().attributes == {
        "linea": "Nendoroid",
        "numero": 1234,
        "escala": "1/7",
        "peso": 0.5,
        "edicion_limitada": True,
    }


def test_add_page_renders_one_typed_field_per_property(admin_client):
    figure = ProductTypeFactory(code="figure", attribute_schema=FIGURE_SCHEMA)

    response = admin_client.get(reverse(ADD), {"product_type": figure.pk})

    form = response.context["adminform"].form
    assert response.status_code == 200
    assert form["attr_linea"].label == "Línea"
    assert form["attr_numero"].field.widget.input_type == "number"
    assert form["attr_escala"].field.widget.__class__.__name__ == "Select"
    assert form["attr_edicion_limitada"].field.widget.input_type == "checkbox"
    assert "attributes" not in form.fields


def test_change_page_shows_current_values_and_saves_edits(admin_client):
    figure = ProductTypeFactory(code="figure", attribute_schema=FIGURE_SCHEMA)
    product = ProductFactory(
        product_type=figure, attributes={"numero": 7, "linea": "Pop Up"}
    )

    page = admin_client.get(reverse(CHANGE, args=[product.pk]))
    form = page.context["adminform"].form
    assert form["attr_numero"].value() == 7
    assert form["attr_linea"].value() == "Pop Up"

    response = admin_client.post(
        reverse(CHANGE, args=[product.pk]),
        product_form(figure, slug=product.slug, attr_numero="8"),
    )

    assert response.status_code == 302
    product.refresh_from_db()
    assert product.attributes == {"numero": 8, "edicion_limitada": False}


def test_schema_constraint_error_lands_on_the_field(admin_client):
    schema = {
        "type": "object",
        "properties": {"numero": {"type": "integer", "minimum": 1}},
    }
    figure = ProductTypeFactory(code="figure", attribute_schema=schema)

    response = admin_client.post(reverse(ADD), product_form(figure, attr_numero="0"))

    assert response.status_code == 200
    assert "attr_numero" in response.context["adminform"].form.errors
    assert not Product.objects.exists()


def test_p3_v11_unrecognised_schema_falls_back_to_json(admin_client):
    schema = {
        "type": "object",
        "properties": {
            "linea": {"type": "string"},
            "etiquetas": {"type": "array", "items": {"type": "string"}},
        },
    }
    figure = ProductTypeFactory(code="figure", attribute_schema=schema)

    response = admin_client.get(reverse(ADD), {"product_type": figure.pk})

    assert response.status_code == 200
    form = response.context["adminform"].form
    assert form["attr_etiquetas"].field.widget.__class__.__name__ == "Textarea"
    assert "attr_etiquetas" in response.content.decode()

    saved = admin_client.post(
        reverse(ADD),
        product_form(figure, attr_linea="Pop Up", attr_etiquetas='["a", "b"]'),
    )
    assert saved.status_code == 302
    assert Product.objects.get().attributes == {
        "linea": "Pop Up",
        "etiquetas": ["a", "b"],
    }


@pytest.mark.parametrize("schema", [{}, {"type": "object"}, {"properties": []}])
def test_p3_v11_unreadable_schema_shows_the_raw_json_field(admin_client, schema):
    figure = ProductTypeFactory(code="figure", attribute_schema=schema)

    response = admin_client.get(reverse(ADD), {"product_type": figure.pk})

    assert response.status_code == 200
    assert "attributes" in response.context["adminform"].form.fields


def test_attributes_outside_the_schema_fall_back_to_json(admin_client):
    figure = ProductTypeFactory(code="figure", attribute_schema=FIGURE_SCHEMA)
    product = ProductFactory(product_type=figure, attributes={"numero": 1})
    Product.objects.filter(pk=product.pk).update(attributes={"viejo": 1})

    response = admin_client.get(reverse(CHANGE, args=[product.pk]))

    assert response.status_code == 200
    assert "attributes" in response.context["adminform"].form.fields
