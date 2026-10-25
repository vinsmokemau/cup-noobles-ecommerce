import pytest

from apps.catalog.models import Variant
from apps.inventory.errors import InsufficientStock


def test_p4_v10_insufficient_stock_payload():
    variant = Variant(sku="NEN-LINK-001", price_cents=10000)

    with pytest.raises(InsufficientStock) as raised:
        raise InsufficientStock(variant, 5, 2)

    assert raised.value.variant is variant
    assert raised.value.requested == 5
    assert raised.value.available == 2
