import pytest

from apps.inventory import services
from apps.inventory.models import StockItem, StockLedger
from tests.factories.catalog import VariantFactory
from tests.factories.inventory import (
    LocationFactory,
    assert_stock_integrity,
    holding_order,
    stocked_variant,
)

pytestmark = pytest.mark.django_db


def make_receipt():
    variant = VariantFactory()
    services.receive_stock(variant, LocationFactory(), 4, note="proveedor")
    return variant


def make_sale_online():
    variant = stocked_variant(on_hand=4)
    services.commit_reservations(holding_order(variant, 2))
    return variant


def adjust_with(reason):
    def make():
        variant = stocked_variant(on_hand=4)
        services.adjust_stock(
            variant, LocationFactory(), -1, reason=reason, actor=None, note="x"
        )
        return variant

    return make


@pytest.mark.parametrize(
    ("reason", "make"),
    [
        ("receipt", make_receipt),
        ("sale_online", make_sale_online),
        ("adjustment", adjust_with("adjustment")),
        ("damage", adjust_with("damage")),
        ("count_correction", adjust_with("count_correction")),
    ],
)
def test_p4_v15_every_on_hand_change_has_one_ledger_row(reason, make):
    variant = make()

    row = StockLedger.objects.filter(stock_item__variant=variant, reason=reason).get()
    assert row.balance_after == StockItem.objects.get(variant=variant).on_hand
    assert_stock_integrity(variant)
