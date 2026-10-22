"""CR-05: physical stock changes only through the inventory services (SPEC.md §4.6)."""

import pytest

from tests.architecture.ast_scan import field_write_violations, scan_apps

STOCK_FIELDS = {"on_hand", "reserved"}
STOCK_ALLOWLIST = {"apps/inventory/services.py"}


def check_source(path: str, source: str) -> list[str]:
    """`path` is relative to `api/`, with forward slashes."""
    return field_write_violations(path, source, STOCK_FIELDS, STOCK_ALLOWLIST)


def test_stock_mutation_confined_to_the_inventory_services():
    assert scan_apps(STOCK_FIELDS, STOCK_ALLOWLIST) == []


@pytest.mark.parametrize(
    "source",
    [
        "stock_item.on_hand -= 1",
        "stock_item.reserved = 0",
        "stock_item.on_hand: int = 3",
        'setattr(stock_item, "on_hand", 3)',
        'setattr(stock_item, "reserved", 3)',
        "StockItem.objects.filter(pk=1).update(on_hand=F('on_hand') - 1)",
        "StockItem.objects.update(reserved=0)",
    ],
)
def test_stock_write_is_found_however_it_is_written(source):
    assert check_source("apps/orders/services.py", source)


@pytest.mark.parametrize(
    "source",
    [
        "available = stock_item.on_hand - stock_item.reserved",
        "StockItem.objects.update(sku='x')",
        'setattr(stock_item, "sku", 3)',
    ],
)
def test_reading_stock_is_not_flagged(source):
    assert check_source("apps/orders/services.py", source) == []


def test_only_the_inventory_services_may_write_stock():
    assert check_source("apps/inventory/services.py", "item.on_hand -= 1") == []
    assert check_source("apps/inventory/models.py", "item.on_hand -= 1")
