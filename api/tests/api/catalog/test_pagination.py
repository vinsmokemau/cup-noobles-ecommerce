"""P5-V12: the product list walks by cursor."""

import pytest

from apps.catalog.services import publish_product
from tests.factories.catalog import ProductFactory

pytestmark = pytest.mark.django_db

URL = "/api/catalog/products/"


def walk(api_client, *, page_size, between_pages=None):
    """Every slug seen when following `next` from the first page, in order."""
    seen, url, page = [], f"{URL}?page_size={page_size}", 0
    while url:
        response = api_client.get(url)
        assert response.status_code == 200
        seen += [row["slug"] for row in response.json()["results"]]
        url = response.json()["next"]
        page += 1
        if between_pages and url:
            between_pages(page)
    return seen


def test_p5_v12_cursor_stable(api_client):
    products = [ProductFactory(published=True) for _ in range(10)]
    early_draft = ProductFactory(name="Se publica a medias")

    def publish_midway(page):
        if page == 1:
            publish_product(early_draft)
            ProductFactory(published=True, name="Llega a medias")

    seen = walk(api_client, page_size=3, between_pages=publish_midway)

    assert len(seen) == len(set(seen)), "a product appeared on two pages"
    assert {p.slug for p in products} <= set(seen), "a product was skipped"
    assert seen[0] == products[-1].slug


def test_pages_are_newest_first_and_link_both_ways(api_client):
    products = [ProductFactory(published=True) for _ in range(5)]

    first = api_client.get(f"{URL}?page_size=2").json()
    second = api_client.get(first["next"]).json()

    assert [r["slug"] for r in first["results"]] == [products[4].slug, products[3].slug]
    assert [r["slug"] for r in second["results"]] == [
        products[2].slug,
        products[1].slug,
    ]
    assert first["previous"] is None
    assert second["previous"] is not None


def test_page_size_defaults_to_24_and_caps_at_48(api_client):
    for _ in range(50):
        ProductFactory(published=True)

    assert len(api_client.get(URL).json()["results"]) == 24
    assert len(api_client.get(f"{URL}?page_size=48").json()["results"]) == 48
    assert len(api_client.get(f"{URL}?page_size=500").json()["results"]) == 48


def test_a_bad_cursor_is_a_400(api_client):
    response = api_client.get(f"{URL}?cursor=basura")

    assert response.status_code == 400
    assert "cursor" in response.json()
