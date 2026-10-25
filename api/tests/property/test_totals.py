from types import SimpleNamespace

from hypothesis import given
from hypothesis import strategies as st

from apps.orders.pricing import compute_totals

cents = st.integers(min_value=0, max_value=10_000_000)
lines_strategy = st.lists(
    st.builds(
        SimpleNamespace,
        unit_price_cents=cents,
        quantity=st.integers(min_value=1, max_value=20),
    ),
    max_size=8,
)


@given(lines=lines_strategy, shipping=cents, data=st.data())
def test_p7_v17_totals_properties(lines, shipping, data):
    subtotal = sum(line.unit_price_cents * line.quantity for line in lines)
    discount = data.draw(st.integers(min_value=0, max_value=subtotal + shipping))

    totals = compute_totals(lines, shipping, discount)

    values = (
        totals.subtotal_cents,
        totals.shipping_cents,
        totals.discount_cents,
        totals.total_cents,
        totals.tax_included_cents,
    )
    assert all(type(value) is int and value >= 0 for value in values)
    assert totals.subtotal_cents == subtotal
    assert totals.total_cents == subtotal + shipping - discount
    assert totals.tax_included_cents == round(totals.total_cents * 16 / 116)
