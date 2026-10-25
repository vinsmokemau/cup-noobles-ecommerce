"""P5-V15: pre-launch mode hides the catalog from the public (T5.7, G32, ADR-0038)."""

import pytest

from apps.accounts.models import Customer
from apps.core.models import SiteSetting

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


@pytest.fixture
def staff():
    return Customer.objects.create_user(
        email="staff@cupnoobles.test", password="x", is_staff=True
    )


def slug_of(client) -> str:
    return client.get("/api/catalog/products/").json()["results"][0]["slug"]


@pytest.mark.parametrize("url", CATALOG_URLS)
def test_p5_v15_prelaunch_hides_catalog(
    api_client, auth_client, staff, catalog_dataset, url
):
    slug = slug_of(api_client)
    url = url.format(slug=slug)
    SiteSetting.objects.update_or_create(pk=1, defaults={"prelaunch_mode": True})

    anonymous = api_client.get(url)
    staff_response = auth_client(staff).get(url)

    assert anonymous.status_code == 503
    assert anonymous.json() == {"prelaunch": True}
    assert cache_directives(anonymous) == {"no-store"}
    assert staff_response.status_code == 200
    assert "private" in cache_directives(staff_response)
    assert "public" not in cache_directives(staff_response)


def test_p5_v15_prelaunch_errors_are_never_public(
    api_client, auth_client, staff, catalog_dataset, prelaunch_on
):
    anonymous = api_client.get("/api/catalog/products/no-such-product/")
    missing = auth_client(staff).get("/api/catalog/products/no-such-product/")

    assert (anonymous.status_code, missing.status_code) == (503, 404)
    assert "public" not in cache_directives(anonymous)
    assert "public" not in cache_directives(missing)


def test_p5_v15_customer_session_is_not_staff(
    api_client, auth_client, catalog_dataset, prelaunch_on
):
    customer = Customer.objects.create_user(
        email="cliente@cupnoobles.test", password="x"
    )

    response = auth_client(customer).get("/api/catalog/products/")

    assert response.status_code == 503


@pytest.mark.parametrize("row", ["off", "missing"])
def test_p5_v15_mode_off_is_public(api_client, catalog_dataset, row):
    if row == "off":
        SiteSetting.objects.update_or_create(pk=1, defaults={"prelaunch_mode": False})
    else:
        SiteSetting.objects.all().delete()

    response = api_client.get("/api/catalog/products/")

    assert response.status_code == 200
    assert cache_directives(response) == {"public", "max-age=60"}


def test_p5_v15_other_endpoints_stay_up(api_client, prelaunch_on):
    assert api_client.get("/api/health/").status_code == 200
