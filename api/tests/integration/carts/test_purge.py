from datetime import UTC, datetime, timedelta
from io import StringIO

import pytest
from django.core.management import call_command

from apps.carts.models import Cart, CartLine
from tests.factories.carts import CartFactory, CartLineFactory
from tests.factories.orders import OrderFactory

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
SIXTY_DAYS = timedelta(days=60)


def cart_untouched_since(moment, **fields):
    cart = CartFactory(**fields)
    CartLineFactory(cart=cart)
    # `updated_at` is auto_now, so only a queryset update can place it in the past.
    Cart.objects.filter(pk=cart.pk).update(updated_at=moment)
    return cart


def purge() -> str:
    out = StringIO()
    call_command("purge_stale_carts", stdout=out)
    return out.getvalue()


def test_p7_v15_stale_cart_boundary(clock):
    clock.travel(NOW)
    at_limit = cart_untouched_since(NOW - SIXTY_DAYS)
    just_over = cart_untouched_since(NOW - SIXTY_DAYS - timedelta(seconds=1))
    converted = cart_untouched_since(
        NOW - SIXTY_DAYS - timedelta(days=30), converted_order=OrderFactory()
    )

    purge()

    survivors = set(Cart.objects.values_list("pk", flat=True))
    assert survivors == {at_limit.pk, converted.pk}
    assert just_over.pk not in survivors
    # The purged cart's line is gone with it; the kept carts keep theirs.
    assert CartLine.objects.filter(cart=just_over).count() == 0
    assert CartLine.objects.filter(cart__in=[at_limit, converted]).count() == 2


def test_purge_stale_carts_is_idempotent(clock):
    clock.travel(NOW)
    cart_untouched_since(NOW - SIXTY_DAYS - timedelta(days=1))
    fresh = cart_untouched_since(NOW - timedelta(days=1))

    purge()
    purge()

    assert list(Cart.objects.values_list("pk", flat=True)) == [fresh.pk]
