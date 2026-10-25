from types import SimpleNamespace

import pytest

from apps.orders.pricing import compute_totals


def test_p7_v06_iva_example():
    lines = [SimpleNamespace(unit_price_cents=58000, quantity=2)]

    totals = compute_totals(lines, shipping_cents=0, discount_cents=0)

    assert totals.total_cents == 116000
    assert totals.tax_included_cents == 16000


@pytest.mark.parametrize(
    ("price", "quantity", "shipping", "discount"),
    [
        (1000, 1, -1, 0),
        (1000, 1, 0, -1),
        (-1, 1, 0, 0),
        (1000, -1, 0, 0),
        (1000, 1, 0, 1001),
    ],
)
def test_compute_totals_rejects_impossible_inputs(price, quantity, shipping, discount):
    line = SimpleNamespace(unit_price_cents=price, quantity=quantity)
    with pytest.raises(ValueError):
        compute_totals([line], shipping, discount)
