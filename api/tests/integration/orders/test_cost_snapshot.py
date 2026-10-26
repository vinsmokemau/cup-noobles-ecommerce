"""The unit-cost snapshot on `order_line` (SPEC.md T8.9, G33, REQ-063)."""

import pytest

from apps.orders.models import OrderLine
from tests.factories.inventory import stocked_variant
from tests.factories.orders import cart_with, place_order

pytestmark = pytest.mark.django_db


def test_p8_v21_unit_cost_snapshot(dev_defaults):
    costed = stocked_variant(5, cost_cents=7000)
    uncosted = stocked_variant(5, cost_cents=None)
    order = place_order(cart_with((costed, 2), (uncosted, 1)))

    lines = {line.sku: line for line in order.lines.all()}
    assert lines[costed.sku].unit_cost_cents == 7000
    assert lines[uncosted.sku].unit_cost_cents is None

    # A later cost change never alters the snapshot.
    costed.cost_cents = 9999
    costed.save()
    assert OrderLine.objects.get(pk=lines[costed.sku].pk).unit_cost_cents == 7000
