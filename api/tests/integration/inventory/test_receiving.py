import pytest
from django.urls import reverse

from apps.inventory.models import StockItem, StockLedger
from tests.factories.catalog import VariantFactory
from tests.factories.inventory import (
    LocationFactory,
    assert_stock_integrity,
    stocked_variant,
)

pytestmark = pytest.mark.django_db

RECEIVE = "admin:inventory_stockitem_receive"
CHANGELIST = "admin:inventory_stockitem_changelist"


def receive(admin_client, variant, location, quantity, note=""):
    return admin_client.post(
        reverse(RECEIVE),
        {
            "variant": variant.pk,
            "location": location.pk,
            "quantity": quantity,
            "note": note,
        },
    )


def test_p4_v19_receive_goods_admin_action(admin_client, admin_user):
    location = LocationFactory()
    variant = stocked_variant(on_hand=3, location=location)

    response = receive(admin_client, variant, location, 4, note="caja 12")

    assert response.status_code == 302
    item = StockItem.objects.get(variant=variant, location=location)
    assert item.on_hand == 7
    row = StockLedger.objects.get(stock_item=item, reason="receipt", delta=4)
    assert (row.balance_after, row.note) == (7, "caja 12")
    assert row.actor_user_id == admin_user.pk
    assert_stock_integrity(variant)

    # A zero or negative quantity is a form error and changes nothing.
    for quantity in (0, -2):
        response = receive(admin_client, variant, location, quantity)
        assert response.status_code == 200
        assert "quantity" in response.context["form"].errors
    item.refresh_from_db()
    assert item.on_hand == 7
    assert StockLedger.objects.filter(stock_item=item).count() == 2


def test_receiving_creates_the_stock_row_for_a_new_location(admin_client):
    variant = VariantFactory()
    location = LocationFactory()

    response = receive(admin_client, variant, location, 5)

    assert response.status_code == 302
    assert StockItem.objects.get(variant=variant, location=location).on_hand == 5


def test_receive_page_has_no_on_hand_field_and_changelist_links_to_it(admin_client):
    page = admin_client.get(reverse(RECEIVE))

    assert set(page.context["form"].fields) == {
        "variant",
        "location",
        "quantity",
        "note",
    }
    changelist = admin_client.get(reverse(CHANGELIST))
    assert reverse(RECEIVE) in changelist.content.decode()


def test_receive_page_needs_change_permission(client, django_user_model):
    staff = django_user_model.objects.create_user(
        "viewer@example.com", password="pw", is_staff=True
    )
    client.force_login(staff)

    assert client.get(reverse(RECEIVE)).status_code == 403
