"""P7-V03: the cart stores no prices; every read takes the variant's current price (T7.3)."""

import pytest

from apps.carts.models import CartLine
from tests.factories.carts import CartLineFactory
from tests.factories.catalog import VariantFactory

pytestmark = pytest.mark.django_db


def test_p7_v03_price_change_reflected(cart_client):
    variant = VariantFactory(price_cents=25000)
    CartLineFactory(cart=cart_client.cart, variant=variant, quantity=2)

    before = cart_client.get("/api/cart/").json()
    assert before["lines"][0]["unit_price_cents"] == 25000
    assert before["lines"][0]["line_total_cents"] == 50000
    assert before["totals"]["subtotal_cents"] == 50000

    variant.price_cents = 31000
    variant.save(update_fields=["price_cents"])

    after = cart_client.get("/api/cart/").json()
    assert after["lines"][0]["unit_price_cents"] == 31000
    assert after["lines"][0]["line_total_cents"] == 62000
    assert after["totals"]["subtotal_cents"] == 62000
    assert after["totals"]["total_cents"] == 62000
    assert after["totals"]["tax_included_cents"] == 8552  # round(62000 * 16 / 116)


def test_cart_line_has_no_price_column():
    assert {f.name for f in CartLine._meta.get_fields()} == {
        "id",
        "cart",
        "variant",
        "quantity",
        "added_at",
    }


def test_totals_sum_every_line(cart_client):
    CartLineFactory(
        cart=cart_client.cart, variant=VariantFactory(price_cents=10000), quantity=3
    )
    CartLineFactory(
        cart=cart_client.cart, variant=VariantFactory(price_cents=4550), quantity=1
    )

    totals = cart_client.get("/api/cart/").json()["totals"]

    assert totals["subtotal_cents"] == 34550
    assert totals["shipping_cents"] == 0
    assert totals["discount_cents"] == 0
    assert totals["total_cents"] == 34550
