import pytest

from apps.inventory import services
from apps.inventory.errors import AdjustmentBelowReserved
from apps.inventory.models import StockItem, StockLedger
from tests.factories.accounts import CustomerFactory
from tests.factories.inventory import (
    LocationFactory,
    assert_stock_integrity,
    holding_order,
    stocked_variant,
)

pytestmark = pytest.mark.django_db


def test_p4_v12_adjust_below_reserved_rejected():
    variant = stocked_variant(on_hand=3)
    holding_order(variant, 2)
    location = LocationFactory()
    actor = CustomerFactory()

    with pytest.raises(AdjustmentBelowReserved):
        services.adjust_stock(
            variant, location, -2, reason="damage", actor=actor, note="se cayó"
        )
    assert StockItem.objects.get(variant=variant).on_hand == 3

    services.adjust_stock(
        variant, location, -1, reason="damage", actor=actor, note="se cayó"
    )

    assert StockItem.objects.get(variant=variant).on_hand == 2
    row = StockLedger.objects.get(reason="damage")
    assert (row.delta, row.balance_after, row.note) == (-1, 2, "se cayó")
    assert row.actor_user_id == actor.pk
    assert_stock_integrity(variant)


def test_an_adjustment_cannot_make_on_hand_negative():
    variant = stocked_variant(on_hand=1)

    with pytest.raises(AdjustmentBelowReserved):
        services.adjust_stock(
            variant, LocationFactory(), -2, reason="adjustment", actor=None, note=""
        )


def test_an_unknown_adjustment_reason_is_rejected():
    variant = stocked_variant(on_hand=1)

    with pytest.raises(ValueError, match="reason"):
        services.adjust_stock(
            variant, LocationFactory(), 1, reason="sale_online", actor=None, note=""
        )
    assert not StockLedger.objects.filter(reason="sale_online").exists()
