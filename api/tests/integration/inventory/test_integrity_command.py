import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from apps.inventory.models import StockItem
from tests.factories.inventory import holding_order, stocked_variant

pytestmark = pytest.mark.django_db


def raw_update(variant, column, value):
    with connection.cursor() as cursor:
        cursor.execute(
            f"UPDATE stock_item SET {column} = %s WHERE variant_id = %s",
            [value, variant.pk],
        )


def test_p4_v07_check_stock_integrity(capsys):
    clean = stocked_variant(on_hand=5)
    holding_order(clean, 2)
    drifted = stocked_variant(on_hand=4)

    call_command("check_stock_integrity")
    assert "ok" in capsys.readouterr().out

    raw_update(drifted, "on_hand", 9)

    with pytest.raises(CommandError) as raised:
        call_command("check_stock_integrity")
    item = StockItem.objects.get(variant=drifted)
    message = str(raised.value)
    assert f"stock_item {item.pk} " in message
    assert drifted.sku in message
    assert clean.sku not in message


def test_p4_v07_reserved_out_of_step_with_held_reservations_is_named():
    variant = stocked_variant(on_hand=5)
    holding_order(variant, 2)
    raw_update(variant, "reserved", 3)

    with pytest.raises(CommandError) as raised:
        call_command("check_stock_integrity")

    item = StockItem.objects.get(variant=variant)
    assert f"stock_item {item.pk} " in str(raised.value)
    assert "reserved is 3" in str(raised.value)
