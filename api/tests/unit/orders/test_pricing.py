from types import SimpleNamespace

from apps.orders.pricing import compute_totals


def test_p7_v06_iva_example():
    lines = [SimpleNamespace(unit_price_cents=58000, quantity=2)]

    totals = compute_totals(lines, shipping_cents=0, discount_cents=0)

    assert totals.total_cents == 116000
    assert totals.tax_included_cents == 16000
