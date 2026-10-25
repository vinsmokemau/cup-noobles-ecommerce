import pytest
from django.contrib import admin
from django.urls import reverse

from apps.inventory.models import StockItem, StockLedger
from tests.factories.inventory import assert_stock_integrity, stocked_variant

pytestmark = pytest.mark.django_db

CHANGELIST = "admin:inventory_stockitem_changelist"
CHANGE = "admin:inventory_stockitem_change"
LEDGER = "admin:inventory_stockledger_changelist"


def adjust(admin_client, item, **fields):
    return admin_client.post(
        reverse(CHANGELIST),
        {
            "action": "adjust",
            "_selected_action": [item.pk],
            "apply": "1",
            **fields,
        },
    )


def test_p4_v18_no_editable_on_hand(admin_client, admin_user):
    variant = stocked_variant(on_hand=5)
    item = StockItem.objects.get(variant=variant)

    page = admin_client.get(reverse(CHANGE, args=[item.pk]))
    form = page.context["adminform"].form
    assert "on_hand" not in form.fields
    assert "reserved" not in form.fields

    # A forged `on_hand` in the POST body changes nothing, and writes no ledger row.
    admin_client.post(
        reverse(CHANGE, args=[item.pk]), {"safety_stock": 1, "on_hand": 99}
    )
    item.refresh_from_db()
    assert (item.on_hand, item.safety_stock) == (5, 1)
    assert StockLedger.objects.filter(stock_item=item).count() == 1

    # The adjust action goes through `adjust_stock`: ledger row with reason, note and actor.
    response = adjust(admin_client, item, delta="-2", reason="damage", note="se cayó")
    assert response.status_code == 302
    item.refresh_from_db()
    assert item.on_hand == 3
    row = StockLedger.objects.get(reason="damage")
    assert (row.delta, row.balance_after, row.note) == (-2, 3, "se cayó")
    assert row.actor_user_id == admin_user.pk
    assert_stock_integrity(variant)


def test_adjust_page_shows_the_form(admin_client):
    item = StockItem.objects.get(variant=stocked_variant(on_hand=2))

    response = admin_client.post(
        reverse(CHANGELIST), {"action": "adjust", "_selected_action": [item.pk]}
    )

    assert response.status_code == 200
    assert "delta" in response.context["form"].fields


def test_adjust_below_reserved_is_a_form_error(admin_client):
    from tests.factories.inventory import holding_order

    variant = stocked_variant(on_hand=3)
    holding_order(variant, 2)
    item = StockItem.objects.get(variant=variant)

    response = adjust(admin_client, item, delta="-2", reason="damage", note="x")

    assert response.status_code == 200
    assert "delta" in response.context["form"].errors
    item.refresh_from_db()
    assert item.on_hand == 3


def test_adjust_rejects_zero_and_missing_note(admin_client):
    item = StockItem.objects.get(variant=stocked_variant(on_hand=3))

    response = adjust(admin_client, item, delta="0", reason="adjustment", note="")

    assert {"delta", "note"} <= set(response.context["form"].errors)
    assert StockLedger.objects.count() == 1


def test_stock_ledger_admin_is_read_only_and_filters_by_variant(
    admin_client, rf, admin_user
):
    kept = stocked_variant(on_hand=4)
    other = stocked_variant(on_hand=7)
    model_admin = admin.site._registry[StockLedger]
    request = rf.get("/")
    request.user = admin_user
    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_change_permission(request)
    assert not model_admin.has_delete_permission(request)

    response = admin_client.get(
        reverse(LEDGER), {"stock_item__variant__id__exact": kept.pk}
    )

    assert response.status_code == 200
    deltas = [row.delta for row in response.context["cl"].result_list]
    assert deltas == [4]
    assert other.pk != kept.pk


def test_adjust_needs_exactly_one_selected_row(admin_client):
    first = StockItem.objects.get(variant=stocked_variant(on_hand=2))
    second = StockItem.objects.get(variant=stocked_variant(on_hand=3))

    response = admin_client.post(
        reverse(CHANGELIST),
        {"action": "adjust", "_selected_action": [first.pk, second.pk]},
        follow=True,
    )

    messages = [str(message) for message in response.context["messages"]]
    assert messages == ["Elige un solo registro de stock para ajustar."]
    assert StockLedger.objects.count() == 2


def test_adjust_shows_a_service_rejection_as_a_form_error(admin_client, monkeypatch):
    from apps.inventory import admin as inventory_admin
    from apps.inventory.errors import InvalidQuantity

    def refuse(*args, **kwargs):
        raise InvalidQuantity("cantidad inválida")

    monkeypatch.setattr(inventory_admin, "adjust_stock", refuse)
    item = StockItem.objects.get(variant=stocked_variant(on_hand=3))

    response = adjust(admin_client, item, delta="-1", reason="damage", note="x")

    assert response.context["form"].errors["delta"] == ["cantidad inválida"]


def test_available_column_never_goes_negative(admin_client):
    variant = stocked_variant(on_hand=2)
    item = StockItem.objects.get(variant=variant)
    StockItem.objects.filter(pk=item.pk).update(safety_stock=5)
    model_admin = admin.site._registry[StockItem]

    item.refresh_from_db()

    assert model_admin.available(item) == 0


def test_p4_v20_bin_location_editable(admin_client):
    variant = stocked_variant(on_hand=5)
    item = StockItem.objects.get(variant=variant)
    ledger_rows = StockLedger.objects.filter(stock_item=item).count()

    page = admin_client.get(reverse(CHANGE, args=[item.pk]))
    assert "bin_location" in page.context["adminform"].form.fields

    response = admin_client.post(
        reverse(CHANGE, args=[item.pk]),
        {"safety_stock": item.safety_stock, "bin_location": "A-03-2", "on_hand": 99},
    )

    assert response.status_code == 302
    item.refresh_from_db()
    assert (item.bin_location, item.on_hand) == ("A-03-2", 5)
    assert StockLedger.objects.filter(stock_item=item).count() == ledger_rows
    assert_stock_integrity(variant)


def test_saving_the_form_never_writes_a_stale_stock_count(admin_client, monkeypatch):
    item = StockItem.objects.get(variant=stocked_variant(on_hand=5))
    stock_admin = admin.site._registry[StockItem]
    original = stock_admin.get_object

    def stale_object(request, object_id, from_field=None):
        obj = original(request, object_id, from_field)
        # A sale commits after the page loaded the row and before the save.
        StockItem.objects.filter(pk=obj.pk).update(on_hand=3, reserved=2)
        return obj

    monkeypatch.setattr(stock_admin, "get_object", stale_object)
    admin_client.post(
        reverse(CHANGE, args=[item.pk]), {"safety_stock": 1, "bin_location": "B-1"}
    )

    item.refresh_from_db()
    assert (item.on_hand, item.reserved, item.bin_location) == (3, 2, "B-1")
