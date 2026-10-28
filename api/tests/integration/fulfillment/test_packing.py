"""The packing view shows each line's bin location and moves no stock (SPEC.md 10.17, P10-V26)."""

import pytest
from django.urls import reverse

from apps.inventory.models import StockItem, StockLedger
from tests.factories.orders import order_through_checkout

pytestmark = pytest.mark.django_db


def test_p10_v26_packing_view_bin_locations(dev_defaults, admin_client):
    order = order_through_checkout("preparing", quantity=2)
    line = order.lines.get()
    item = StockItem.objects.get(variant=line.variant)
    StockItem.objects.filter(pk=item.pk).update(bin_location="A-03-2")
    before = (
        StockItem.objects.values_list("on_hand", "reserved").get(pk=item.pk),
        StockLedger.objects.count(),
    )

    change = admin_client.get(reverse("admin:orders_order_change", args=[order.pk]))
    packing_url = reverse("admin:orders_order_packing", args=[order.pk])
    assert packing_url in change.content.decode()

    page = admin_client.get(packing_url)

    assert page.status_code == 200
    html = page.content.decode()
    assert line.sku in html
    assert line.product_name in html
    assert "A-03-2" in html
    assert [
        (r["sku"], r["quantity"], r["bin_location"]) for r in page.context["lines"]
    ] == [(line.sku, 2, "A-03-2")]
    after = (
        StockItem.objects.values_list("on_hand", "reserved").get(pk=item.pk),
        StockLedger.objects.count(),
    )
    assert after == before


def test_packing_view_is_only_for_preparing_orders(dev_defaults, admin_client):
    order = order_through_checkout("paid")

    change = admin_client.get(reverse("admin:orders_order_change", args=[order.pk]))
    response = admin_client.get(reverse("admin:orders_order_packing", args=[order.pk]))

    assert "packing-link" not in change.content.decode()
    assert response.status_code == 302
