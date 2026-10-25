"""The product detail (T5.1): P5-V09 and the payload."""

import pytest

from tests.factories.catalog import CategoryFactory, ProductFactory, ProductImageFactory

pytestmark = pytest.mark.django_db


def detail(api_client, slug):
    return api_client.get(f"/api/catalog/products/{slug}/")


def test_p5_v09_draft_and_archived_hidden(api_client, catalog_dataset):
    listed = [
        r["slug"] for r in api_client.get("/api/catalog/products/").json()["results"]
    ]
    searched = [
        r["slug"] for r in api_client.get("/api/catalog/search/?q=borrador").json()
    ]

    for hidden in (catalog_dataset.draft, catalog_dataset.archived):
        assert hidden.slug not in listed
        assert hidden.slug not in searched
        assert detail(api_client, hidden.slug).status_code == 404
    assert detail(api_client, "no-existe").status_code == 404
    assert detail(api_client, catalog_dataset.nendoroid.slug).status_code == 200


def test_p5_v09_hidden_products_are_not_related(api_client, catalog_dataset):
    body = detail(api_client, "nendoroid-link").json()

    related = {r["slug"] for r in body["related"]}
    assert catalog_dataset.draft.slug not in related
    assert catalog_dataset.archived.slug not in related


def test_detail_payload(api_client, catalog_dataset):
    body = detail(api_client, "figma-zelda").json()

    assert body["name"] == "Figma Zelda"
    assert body["attributes"] == {"linea": "Figma"}
    assert body["product_type"] == "figure"
    assert body["categories"] == [{"slug": "figuras", "name": "Figuras"}]
    assert [v["sku"] for v in body["variants"]] == ["FIG-ZELDA-A", "FIG-ZELDA-B"]
    assert [v["availability"] for v in body["variants"]] == [
        {"status": "low_stock"},
        {"status": "out_of_stock"},
    ]
    assert body["variants"][1]["options"] == {"edicion": "basica"}
    assert body["availability"] == {"status": "low_stock"}


def test_detail_has_no_costs_counts_or_original_images(api_client, catalog_dataset):
    ProductImageFactory(product=catalog_dataset.nendoroid, storage_key="products/a.jpg")

    body = detail(api_client, "nendoroid-link").content.decode()

    for forbidden in ("cost_cents", "on_hand", "reserved", "safety_stock", "barcode"):
        assert forbidden not in body
    assert "products/a.jpg" not in body
    assert "products/a-800.webp" in body


def test_detail_images_name_their_variant(api_client, catalog_dataset):
    variant = catalog_dataset.nendoroid.variants.get()
    ProductImageFactory(product=catalog_dataset.nendoroid, variant=variant, position=5)

    images = detail(api_client, "nendoroid-link").json()["images"]

    assert [i["variant"] for i in images] == [None, str(variant.public_id)]


def test_related_shares_the_franchise_or_a_category(api_client, catalog_dataset):
    # Link and the Figma share the franchise Zelda; the Pokémon box shares nothing.
    related = detail(api_client, "nendoroid-link").json()["related"]
    assert [r["slug"] for r in related] == ["figma-zelda"]

    other = ProductFactory(published=True, categories=[catalog_dataset.cartas])
    related = detail(api_client, "caja-prismatic").json()["related"]
    assert [r["slug"] for r in related] == [other.slug]


def test_related_is_empty_without_franchise_or_category(api_client):
    loner = ProductFactory(published=True)
    ProductFactory(published=True)

    assert detail(api_client, loner.slug).json()["related"] == []


def test_related_is_capped_and_never_the_product_itself(api_client, catalog_dataset):
    category = CategoryFactory()
    me = ProductFactory(published=True, categories=[category])
    for _ in range(12):
        ProductFactory(published=True, categories=[category])

    related = detail(api_client, me.slug).json()["related"]

    assert len(related) == 8
    assert me.slug not in [r["slug"] for r in related]


def test_slug_lookup_ignores_case(api_client, catalog_dataset):
    assert detail(api_client, "FIGMA-Zelda").status_code == 200
