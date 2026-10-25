from datetime import timedelta

import pytest

from apps.inventory import services
from apps.inventory.errors import InvalidQuantity
from apps.inventory.models import StockLedger
from tests.factories.catalog import VariantFactory
from tests.factories.inventory import LocationFactory
from tests.factories.orders import DraftOrderFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("quantity", [0, -1, -50])
def test_p4_v13_invalid_quantity(quantity, django_assert_num_queries):
    variant = VariantFactory.build(pk=1)
    location = LocationFactory.build(pk=1)
    order = DraftOrderFactory.build(pk=1)

    with django_assert_num_queries(0):
        with pytest.raises(InvalidQuantity):
            services.receive_stock(variant, location, quantity)
        with pytest.raises(InvalidQuantity):
            services.reserve(
                order, [(variant, 1), (variant, quantity)], ttl=timedelta(hours=1)
            )
        with pytest.raises(InvalidQuantity):
            services.adjust_stock(
                variant,
                location,
                0,
                reason=StockLedger.Reason.ADJUSTMENT,
                actor=None,
                note="",
            )
