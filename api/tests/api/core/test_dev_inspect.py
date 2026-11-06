"""T13.8: the read-only inspection endpoints `/dev/test/inventory/<sku>/` and
`/dev/test/orders/?email=` (404 where dev tools are off)."""

import importlib
from datetime import date

import pytest
from django.urls import clear_url_caches

from apps.inventory import services
from tests.factories.catalog import VariantFactory
from tests.factories.inventory import (
    LocationFactory,
    StockItemFactory,
    holding_order,
    stocked_variant,
)
from tests.factories.orders import OrderFactory, order_in_state

pytestmark = pytest.mark.django_db


def test_inventory_reports_on_hand_reserved_and_preorder_committed(client):
    variant = stocked_variant(10)
    holding_order(variant, 3)
    variant.preorder_committed = 0
    variant.save()

    response = client.get(f"/dev/test/inventory/{variant.sku}/")

    assert response.status_code == 200
    assert response.json() == {"on_hand": 10, "reserved": 3, "preorder_committed": 0}


def test_inventory_sums_every_location(client):
    variant = stocked_variant(4)
    other = LocationFactory(code="tienda", name="Otra", kind="store")
    StockItemFactory(variant=variant, location=other)
    services.receive_stock(variant, other, 5)

    assert client.get(f"/dev/test/inventory/{variant.sku}/").json()["on_hand"] == 9


def test_inventory_of_a_variant_without_stock_rows_is_zero(client):
    variant = VariantFactory(
        is_preorder=True,
        preorder_limit=5,
        preorder_committed=2,
        expected_release_date=date(2027, 1, 15),
    )

    assert client.get(f"/dev/test/inventory/{variant.sku}/").json() == {
        "on_hand": 0,
        "reserved": 0,
        "preorder_committed": 2,
    }


def test_inventory_unknown_sku_is_404(client):
    assert client.get("/dev/test/inventory/NOPE/").status_code == 404


def test_inventory_is_get_only(client):
    assert client.post("/dev/test/inventory/NOPE/").status_code == 405


def test_orders_lists_number_and_state_for_the_email_only(client):
    mine = order_in_state("paid", email="yo@example.com")
    OrderFactory(email="otro@example.com")

    response = client.get("/dev/test/orders/", {"email": "yo@example.com"})

    assert response.status_code == 200
    assert response.json() == {"orders": [{"number": mine.number, "state": "paid"}]}


def test_orders_without_a_match_is_an_empty_list(client):
    response = client.get("/dev/test/orders/", {"email": "nadie@example.com"})

    assert response.json() == {"orders": []}


def test_orders_requires_an_email(client):
    assert client.get("/dev/test/orders/").status_code == 400


@pytest.mark.parametrize(
    "url", ["/dev/test/inventory/ANY/", "/dev/test/orders/?email=a@b.mx"]
)
def test_routes_are_not_registered_when_dev_tools_are_off(client, settings, url):
    import config.urls

    settings.DEV_TOOLS_ENABLED = False
    clear_url_caches()
    importlib.reload(config.urls)
    try:
        response = client.get(url)
    finally:
        settings.DEV_TOOLS_ENABLED = True
        clear_url_caches()
        importlib.reload(config.urls)

    assert response.status_code == 404
