"""P7-V18: every unsafe cart method requires `X-CSRFToken` (T7.1, T6.2)."""

import pytest

from apps.carts.models import CartLine
from tests.factories.carts import CartLineFactory
from tests.factories.catalog import VariantFactory

pytestmark = pytest.mark.django_db


def test_p7_v18_cart_write_requires_csrf(cart_client):
    variant = VariantFactory()
    cart_client.drop_csrf()

    response = cart_client.post(
        "/api/cart/lines/",
        {"variant_public_id": str(variant.public_id), "quantity": 1},
        format="json",
    )

    assert response.status_code == 403
    assert not CartLine.objects.exists()


def test_p7_v18_every_unsafe_method_is_protected(cart_client):
    line = CartLineFactory(cart=cart_client.cart, quantity=2)
    cart_client.drop_csrf()

    patch = cart_client.patch(
        f"/api/cart/lines/{line.pk}/", {"quantity": 5}, format="json"
    )
    delete = cart_client.delete(f"/api/cart/lines/{line.pk}/")
    fulfillment = cart_client.post(
        "/api/cart/fulfillment/",
        {"method": "delivery", "postal_code": "06700"},
        format="json",
    )

    assert patch.status_code == delete.status_code == fulfillment.status_code == 403
    assert CartLine.objects.get(pk=line.pk).quantity == 2


def test_p7_v18_a_read_sets_the_csrf_cookie(anonymous_cart_client):
    assert anonymous_cart_client.cookies["csrftoken"].value
