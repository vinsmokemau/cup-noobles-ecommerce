"""P5-V10: catalog responses are cacheable for 60 seconds (T5.6)."""

import pytest

pytestmark = pytest.mark.django_db

CATALOG_URLS = [
    "/api/catalog/products/",
    "/api/catalog/products/{slug}/",
    "/api/catalog/categories/",
    "/api/catalog/facets/",
    "/api/catalog/search/?q=nendoroid",
]


def cache_directives(response) -> set[str]:
    return {
        part.strip() for part in response.get("Cache-Control", "").split(",") if part
    }


@pytest.mark.parametrize("url", CATALOG_URLS)
def test_p5_v10_cache_control(api_client, catalog_dataset, url):
    slug = api_client.get("/api/catalog/products/").json()["results"][0]["slug"]

    response = api_client.get(url.format(slug=slug))

    assert response.status_code == 200
    assert cache_directives(response) == {"public", "max-age=60"}


def test_p5_v10_errors_are_not_cached(api_client, catalog_dataset):
    missing = api_client.get("/api/catalog/products/no-such-product/")
    invalid = api_client.get("/api/catalog/search/")

    assert (missing.status_code, invalid.status_code) == (404, 400)
    assert "public" not in cache_directives(missing)
    assert "public" not in cache_directives(invalid)


def test_p5_v10_other_endpoints_are_not_public(api_client):
    # The cart and order endpoints arrive in Phases 6 and 9; the rule is that only the catalog
    # views carry the header, so any other route must not.
    response = api_client.get("/api/health/")

    assert response.status_code == 200
    assert "public" not in cache_directives(response)
