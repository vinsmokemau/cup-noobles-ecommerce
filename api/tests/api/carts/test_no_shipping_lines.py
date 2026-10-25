"""T7.5a: a cart with a `requires_shipping=false` line behaves like any other cart.

The task has no Verify ID of its own (it constrains T7.1, T7.3, T7.4 and T7.6), so these tests
are named for the behavior, not a plan ID.
"""

import pytest

from tests.factories.carts import CartLineFactory
from tests.factories.catalog import VariantFactory
from tests.factories.inventory import stocked_variant

pytestmark = pytest.mark.django_db

FULFILLMENT = "/api/cart/fulfillment/"
LINES = "/api/cart/lines/"


def test_a_no_shipping_variant_can_be_added(cart_client):
    variant = VariantFactory(requires_shipping=False, price_cents=25_000)

    response = cart_client.post(
        LINES,
        {"variant_public_id": str(variant.public_id), "quantity": 2},
        format="json",
    )

    assert response.status_code == 201
    line = response.json()["lines"][0]
    assert (line["quantity"], line["unit_price_cents"], line["line_total_cents"]) == (
        2,
        25_000,
        50_000,
    )


def test_a_no_shipping_line_reports_availability_like_any_other(cart_client):
    CartLineFactory(
        cart=cart_client.cart,
        variant=stocked_variant(on_hand=2, requires_shipping=False),
        quantity=3,
    )

    line = cart_client.get("/api/cart/").json()["lines"][0]

    assert (line["availability"], line["max_available"], line["quantity"]) == (
        "reduced",
        2,
        3,
    )


@pytest.mark.parametrize("requires_shipping", [[False], [False, True]])
def test_a_cart_with_a_no_shipping_line_is_quoted_and_totalled(
    cart_client, dev_defaults, requires_shipping
):
    for flag in requires_shipping:
        CartLineFactory(
            cart=cart_client.cart,
            variant=VariantFactory(requires_shipping=flag, price_cents=50_000),
            quantity=1,
        )

    body = cart_client.post(
        FULFILLMENT, {"method": "delivery", "postal_code": "06700"}, format="json"
    ).json()

    subtotal = 50_000 * len(requires_shipping)
    assert body["totals"]["subtotal_cents"] == subtotal
    assert body["shipping_quote"]["zone"] == "local"
    assert body["totals"]["shipping_cents"] == body["shipping_quote"]["price_cents"]
    assert body["totals"]["total_cents"] == subtotal + body["totals"]["shipping_cents"]
