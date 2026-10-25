"""P7-V16: a cart token reaches only its own lines (T7.1)."""

import pytest

from apps.carts.models import CartLine
from tests.factories.carts import CartFactory, CartLineFactory
from tests.factories.orders import DraftOrderFactory

pytestmark = pytest.mark.django_db


def test_p7_v16_cart_token_isolation(cart_client, anonymous_cart_client):
    other_line = CartLineFactory(cart=CartFactory(), quantity=3)
    url = f"/api/cart/lines/{other_line.pk}/"

    patched = cart_client.patch(url, {"quantity": 1}, format="json")
    deleted = cart_client.delete(url)
    missing = cart_client.delete("/api/cart/lines/999999/")

    assert patched.status_code == deleted.status_code == 404
    assert patched.content == deleted.content == missing.content
    assert CartLine.objects.get(pk=other_line.pk).quantity == 3

    # A client with no cart at all gets the same answer.
    assert anonymous_cart_client.delete(url).status_code == 404
    assert (
        anonymous_cart_client.patch(url, {"quantity": 1}, format="json").status_code
        == 404
    )
    assert CartLine.objects.get(pk=other_line.pk).quantity == 3


def test_a_converted_cart_token_reads_as_no_cart(cart_client):
    CartLineFactory(cart=cart_client.cart)
    cart_client.cart.converted_order = DraftOrderFactory()
    cart_client.cart.save()

    assert cart_client.get("/api/cart/").json()["lines"] == []
