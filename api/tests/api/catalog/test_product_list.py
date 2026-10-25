"""The public product list (T5.1) and its `attr.<key>` filters (T5.2: P5-V01, V02, V06). P5-V03 is
T5.4.
"""

import json

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.catalog.models import Category
from tests.factories.catalog import ProductFactory, ProductTypeFactory
from tests.factories.inventory import stocked_variant

pytestmark = pytest.mark.django_db

URL = "/api/catalog/products/"


def slugs(response) -> list[str]:
    return [row["slug"] for row in response.json()["results"]]


def test_list_returns_active_products_only(api_client, catalog_dataset):
    response = api_client.get(URL)

    assert response.status_code == 200
    assert sorted(slugs(response)) == [
        "caja-prismatic",
        "figma-zelda",
        "nendoroid-link",
    ]


def test_list_payload_has_no_costs_or_counts(api_client, catalog_dataset):
    body = api_client.get(URL).content.decode()

    for forbidden in ("cost_cents", "on_hand", "reserved", "safety_stock", "barcode"):
        assert forbidden not in body


def test_list_card_shape(api_client, catalog_dataset):
    rows = {r["slug"]: r for r in api_client.get(URL).json()["results"]}

    link = rows["nendoroid-link"]
    assert link["product_type"] == "figure"
    assert link["brand"] == {"slug": "good-smile", "name": "Good Smile Company"}
    assert link["franchise"] == {"slug": "zelda", "name": "Zelda"}
    assert link["price_cents"] == 90000
    assert link["availability"] == {"status": "in_stock"}
    assert link["image"]["alt"] == "Link de frente"
    assert [s["width"] for s in link["image"]["sources"]] == [400, 800, 1600]
    assert rows["caja-prismatic"]["brand"] is None
    assert rows["caja-prismatic"]["image"] is None


def test_card_takes_the_cheapest_variant_and_the_best_availability(
    api_client, catalog_dataset
):
    rows = {r["slug"]: r for r in api_client.get(URL).json()["results"]}

    figma = rows["figma-zelda"]
    assert figma["price_cents"] == 130000  # the out-of-stock variant is cheaper
    assert figma["availability"] == {"status": "low_stock"}  # the other has 3
    assert rows["caja-prismatic"]["availability"] == {"status": "out_of_stock"}


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("franchise=zelda", ["figma-zelda", "nendoroid-link"]),
        ("franchise=ZELDA", ["figma-zelda", "nendoroid-link"]),
        ("brand=good-smile", ["figma-zelda", "nendoroid-link"]),
        ("type=tcg_sealed", ["caja-prismatic"]),
        ("category=nendoroid", ["nendoroid-link"]),
        ("category=figuras", ["figma-zelda", "nendoroid-link"]),  # includes descendants
        ("category=cartas&franchise=zelda", []),
        ("franchise=no-existe", []),
        ("min_price=125000", ["figma-zelda"]),
        ("max_price=100000", ["nendoroid-link"]),
        ("min_price=100000&max_price=125000", ["caja-prismatic"]),
        ("in_stock=true", ["figma-zelda", "nendoroid-link"]),
        ("in_stock=false", ["caja-prismatic", "figma-zelda", "nendoroid-link"]),
        ("q=", ["caja-prismatic", "figma-zelda", "nendoroid-link"]),
        ("q=zelda", ["figma-zelda"]),
        ("franchise=zelda&in_stock=true&max_price=100000", ["nendoroid-link"]),
    ],
)
def test_list_filters(api_client, catalog_dataset, query, expected):
    response = api_client.get(f"{URL}?{query}")

    assert response.status_code == 200
    assert sorted(slugs(response)) == expected


def test_price_filter_matches_one_variant_not_two(api_client, catalog_dataset):
    # Figma has variants at 130000 and 150000: none costs 140000, but the range spans both.
    response = api_client.get(f"{URL}?min_price=135000&max_price=145000")

    assert slugs(response) == []


def test_inactive_variants_do_not_count(api_client, catalog_dataset):
    catalog_dataset.nendoroid.variants.update(is_active=False)

    rows = {r["slug"]: r for r in api_client.get(URL).json()["results"]}

    assert rows["nendoroid-link"]["price_cents"] is None
    assert rows["nendoroid-link"]["availability"] == {"status": "out_of_stock"}
    assert "nendoroid-link" not in slugs(api_client.get(f"{URL}?in_stock=true"))
    assert "nendoroid-link" not in slugs(api_client.get(f"{URL}?min_price=0"))


def test_inactive_category_is_not_a_filter(api_client, catalog_dataset):
    Category.objects.filter(pk=catalog_dataset.cartas.pk).update(is_active=False)

    assert slugs(api_client.get(f"{URL}?category=cartas")) == []


@pytest.mark.parametrize(
    "query",
    [
        "min_price=abc",
        "min_price=-1",
        "max_price=1.5",
        "min_price=200&max_price=100",
        "in_stock=quizas",
        "q=" + "x" * 101,
    ],
)
def test_invalid_filters_are_a_400(api_client, catalog_dataset, query):
    response = api_client.get(f"{URL}?{query}")

    assert response.status_code == 400
    assert isinstance(json.loads(response.content), dict)


def test_the_catalog_is_read_only(api_client, catalog_dataset):
    for method in ("post", "put", "patch", "delete"):
        assert getattr(api_client, method)(URL).status_code == 405


def test_p5_v01_attr_filter_and_in_stock(api_client, catalog_dataset):
    figure = catalog_dataset.nendoroid.product_type
    sold_out = ProductFactory(
        published=True,
        slug="nendoroid-sin-stock",
        product_type=figure,
        attributes={"linea": "Nendoroid"},
    )
    stocked_variant(0, product=sold_out, sku="NEN-SOLD-OUT")
    draft = ProductFactory(
        slug="nendoroid-borrador",
        product_type=figure,
        attributes={"linea": "Nendoroid"},
    )
    stocked_variant(4, product=draft, sku="NEN-DRAFT")

    both = api_client.get(f"{URL}?attr.linea=Nendoroid&in_stock=true")
    only_attr = api_client.get(f"{URL}?attr.linea=Nendoroid")

    assert slugs(both) == ["nendoroid-link"]
    assert sorted(slugs(only_attr)) == ["nendoroid-link", "nendoroid-sin-stock"]


def test_attr_filters_combine_with_the_other_filters(api_client, catalog_dataset):
    assert slugs(api_client.get(f"{URL}?attr.linea=Figma&franchise=zelda")) == [
        "figma-zelda"
    ]
    assert slugs(api_client.get(f"{URL}?attr.linea=Figma&franchise=pokemon")) == []
    assert slugs(api_client.get(f"{URL}?attr.linea=Figma&type=figure")) == [
        "figma-zelda"
    ]


def test_attr_value_match_is_exact(api_client, catalog_dataset):
    assert slugs(api_client.get(f"{URL}?attr.linea=nendoroid")) == []
    assert slugs(api_client.get(f"{URL}?attr.linea=Nendo")) == []


def test_attr_filter_is_scoped_by_the_type_filter(api_client, catalog_dataset):
    ProductTypeFactory(code="juego", filterable_keys=["jugadores"])

    assert api_client.get(f"{URL}?attr.jugadores=2").status_code == 200
    assert api_client.get(f"{URL}?type=figure&attr.jugadores=2").status_code == 400
    assert api_client.get(f"{URL}?type=juego&attr.linea=Figma").status_code == 400


def test_attr_filter_reads_the_schema_type(api_client, catalog_dataset):
    funko = ProductTypeFactory(
        code="funko",
        attribute_schema={
            "type": "object",
            "properties": {
                "numero": {"type": "integer"},
                "chase": {"type": "boolean"},
            },
        },
        filterable_keys=["numero", "chase"],
    )
    ProductFactory(
        published=True,
        slug="funko-1",
        product_type=funko,
        attributes={"numero": 7, "chase": True},
    )
    ProductFactory(
        published=True,
        slug="funko-2",
        product_type=funko,
        attributes={"numero": 8, "chase": False},
    )

    assert slugs(api_client.get(f"{URL}?attr.numero=7")) == ["funko-1"]
    assert slugs(api_client.get(f"{URL}?attr.chase=true")) == ["funko-1"]
    assert slugs(api_client.get(f"{URL}?attr.chase=FALSE")) == ["funko-2"]
    assert api_client.get(f"{URL}?attr.numero=siete").status_code == 400
    assert api_client.get(f"{URL}?attr.chase=quizas").status_code == 400


def test_attr_filter_with_an_empty_value_is_ignored(api_client, catalog_dataset):
    response = api_client.get(f"{URL}?attr.linea=")

    assert response.status_code == 200
    assert len(slugs(response)) == 3


@pytest.mark.parametrize(
    "query",
    [
        "attr.__proto__=x",
        "attr.'; DROP TABLE product;--=1",
        "attr.linea' OR '1'='1=x",
        "attr.=x",
        "attr..linea=x",
        "attr.linea.extra=x",
    ],
)
def test_p5_v02_malicious_attr_keys_rejected(api_client, catalog_dataset, query):
    with CaptureQueriesContext(connection) as queries:
        response = api_client.get(f"{URL}?{query}")

    assert response.status_code == 400
    assert not [q for q in queries.captured_queries if '"product"' in q["sql"]], (
        "a rejected key must not reach a product query"
    )
    assert api_client.get(URL).status_code == 200  # the table is still there


def test_p5_v06_non_filterable_key_rejected(api_client, catalog_dataset):
    ProductFactory(
        published=True,
        slug="con-secreto",
        product_type=catalog_dataset.nendoroid.product_type,
        attributes={"linea": "Figma", "secreto": "x"},
    )

    response = api_client.get(f"{URL}?attr.secreto=x")

    assert response.status_code == 400
    assert "attr.secreto" in response.json()
