"""P7-V04, P7-V05, P7-V08, P7-V09: the delivery shipping quote (T7.6), under the §2.5 dev defaults."""

import pytest

from apps.carts.models import Cart
from apps.shipping.services import UnknownPostalCode, quote
from tests.factories.carts import CartLineFactory
from tests.factories.catalog import VariantFactory

pytestmark = pytest.mark.django_db

FULFILLMENT = "/api/cart/fulfillment/"


def set_delivery(client, postal_code):
    return client.post(
        FULFILLMENT,
        {"method": "delivery", "postal_code": postal_code},
        format="json",
    )


def fill(client, price_cents):
    CartLineFactory(
        cart=client.cart, variant=VariantFactory(price_cents=price_cents), quantity=1
    )


def test_p7_v04_zones_differ(cart_client, dev_defaults):
    fill(cart_client, 50_000)

    local = set_delivery(cart_client, "06700").json()
    nacional = set_delivery(cart_client, "97000").json()

    assert local["shipping_quote"]["zone"] == "local"
    assert local["shipping_quote"]["price_cents"] == 9_900
    assert (
        local["shipping_quote"]["eta_min_days"],
        local["shipping_quote"]["eta_max_days"],
    ) == (1, 3)
    assert nacional["shipping_quote"]["zone"] == "nacional"
    assert nacional["shipping_quote"]["price_cents"] == 17_900
    assert local["totals"]["shipping_cents"] == 9_900
    assert nacional["totals"]["total_cents"] == 50_000 + 17_900


def test_p7_v05_free_shipping_above_threshold(cart_client, dev_defaults):
    fill(cart_client, 200_000)

    body = set_delivery(cart_client, "97000").json()

    assert body["shipping_quote"]["price_cents"] == 0
    assert body["totals"]["shipping_cents"] == 0
    assert body["totals"]["total_cents"] == 200_000


@pytest.mark.parametrize(
    ("subtotal_cents", "price_cents"), [(149_999, 17_900), (150_000, 0)]
)
def test_p7_v08_threshold_boundary(
    cart_client, dev_defaults, subtotal_cents, price_cents
):
    fill(cart_client, subtotal_cents)

    body = set_delivery(cart_client, "97000").json()

    assert body["shipping_quote"]["price_cents"] == price_cents


def test_p7_v09_unknown_postal_code(cart_client, dev_defaults):
    fill(cart_client, 50_000)

    response = set_delivery(cart_client, "99999")

    assert response.status_code == 400
    assert response.json()["postal_code"] == ["No encontramos ese código postal."]
    cart_client.cart.refresh_from_db()
    assert cart_client.cart.fulfillment_method is None


def test_p7_v09_unknown_postal_code_raises_in_the_service(dev_defaults):
    with pytest.raises(UnknownPostalCode):
        quote("99999", 50_000)


def test_cart_read_quotes_the_requested_postal_code(cart_client, dev_defaults):
    fill(cart_client, 50_000)
    set_delivery(cart_client, "06700")

    quoted = cart_client.get("/api/cart/?postal_code=97000").json()
    plain = cart_client.get("/api/cart/").json()
    unknown = cart_client.get("/api/cart/?postal_code=99999")
    malformed = cart_client.get("/api/cart/?postal_code=6700")

    assert quoted["shipping_quote"]["zone"] == "nacional"
    assert quoted["totals"]["shipping_cents"] == 17_900
    assert plain["shipping_quote"] is None
    assert plain["totals"]["shipping_cents"] == 0
    assert unknown.status_code == malformed.status_code == 400


def test_a_cart_without_delivery_has_no_quote(cart_client, dev_defaults):
    fill(cart_client, 50_000)

    body = cart_client.get("/api/cart/?postal_code=06700").json()

    assert Cart.objects.get(pk=cart_client.cart.pk).fulfillment_method is None
    assert body["shipping_quote"] is None
