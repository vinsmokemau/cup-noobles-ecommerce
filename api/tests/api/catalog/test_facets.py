"""The facets endpoint (T5.2, P5-V13)."""

import pytest

from tests.factories.catalog import ProductFactory, ProductTypeFactory

pytestmark = pytest.mark.django_db

URL = "/api/catalog/facets/"


def facets(response) -> dict[str, dict]:
    assert response.status_code == 200
    return {row["key"]: row for row in response.json()["facets"]}


def counts(facet: dict) -> dict:
    return {row["value"]: row["count"] for row in facet["values"]}


def test_p5_v13_facets_follow_filterable_keys(api_client, catalog_dataset):
    figure = catalog_dataset.nendoroid.product_type
    figure.attribute_schema = {
        "type": "object",
        "properties": {
            "linea": {"type": "string", "title": "Línea"},
            "escala": {"type": "string"},
            "secreto": {"type": "string"},
        },
    }
    figure.filterable_keys = ["linea", "escala"]
    figure.save()
    ProductFactory(
        published=True,
        slug="figura-escala",
        product_type=figure,
        attributes={"linea": "Nendoroid", "escala": "1/7", "secreto": "x"},
    )

    by_key = facets(api_client.get(f"{URL}?type=figure"))

    assert list(by_key) == ["linea", "escala"]  # the type's keys, in its order
    assert by_key["linea"]["title"] == "Línea"
    assert by_key["escala"]["title"] == "escala"  # no title in the schema: the key
    assert counts(by_key["linea"]) == {"Nendoroid": 2, "Figma": 1}
    assert counts(by_key["escala"]) == {"1/7": 1}

    narrowed = facets(api_client.get(f"{URL}?type=figure&attr.linea=Figma"))

    assert counts(narrowed["linea"]) == {"Figma": 1}  # attr.* filters count
    assert narrowed["escala"]["values"] == []

    in_stock = facets(api_client.get(f"{URL}?type=figure&in_stock=true"))

    assert counts(in_stock["linea"]) == {"Nendoroid": 1, "Figma": 1}


def test_counts_follow_every_active_filter(api_client, catalog_dataset):
    assert counts(facets(api_client.get(f"{URL}?franchise=zelda"))["linea"]) == {
        "Figma": 1,
        "Nendoroid": 1,
    }
    assert facets(api_client.get(f"{URL}?franchise=pokemon")) == {}
    assert facets(api_client.get(f"{URL}?franchise=no-existe")) == {}


def test_values_are_ordered_by_count_then_name(api_client, catalog_dataset):
    for n in range(2):
        ProductFactory(
            published=True,
            slug=f"figma-extra-{n}",
            product_type=catalog_dataset.nendoroid.product_type,
            attributes={"linea": "Figma"},
        )

    values = facets(api_client.get(URL))["linea"]["values"]

    assert [row["value"] for row in values] == ["Figma", "Nendoroid"]


def test_without_a_type_the_keys_come_from_the_matching_products(
    api_client, catalog_dataset
):
    juego = ProductTypeFactory(code="juego", filterable_keys=["jugadores"])
    ProductFactory(
        published=True, slug="catan", product_type=juego, attributes={"jugadores": 4}
    )

    assert list(facets(api_client.get(URL))) == ["linea", "jugadores"]
    assert list(facets(api_client.get(f"{URL}?type=juego"))) == ["jugadores"]
    assert list(facets(api_client.get(f"{URL}?type=figure"))) == ["linea"]
    assert counts(facets(api_client.get(URL))["jugadores"]) == {4: 1}


def test_facets_work_with_a_text_search_and_other_filters(api_client, catalog_dataset):
    # The search filter names its table; the facets must not wrap it in a subquery.
    response = api_client.get(f"{URL}?q=zelda&min_price=1&franchise=zelda")

    assert counts(facets(response)["linea"]) == {"Figma": 1}


def test_hidden_products_are_not_counted(api_client, catalog_dataset):
    figure = catalog_dataset.nendoroid.product_type
    ProductFactory(slug="oculto", product_type=figure, attributes={"linea": "Oculto"})

    assert "Oculto" not in counts(facets(api_client.get(URL))["linea"])


@pytest.mark.parametrize(
    "query", ["attr.__proto__=x", "attr.secreto=x", "min_price=abc", "in_stock=quizas"]
)
def test_invalid_queries_are_a_400(api_client, catalog_dataset, query):
    assert api_client.get(f"{URL}?{query}").status_code == 400


def test_facets_are_read_only_and_show_no_stock(api_client, catalog_dataset):
    body = api_client.get(URL).content.decode()

    for forbidden in ("cost_cents", "on_hand", "reserved", "available"):
        assert forbidden not in body
    for method in ("post", "put", "patch", "delete"):
        assert getattr(api_client, method)(URL).status_code == 405
