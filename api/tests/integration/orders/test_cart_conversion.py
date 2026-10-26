"""A cart converts at checkout (SPEC.md T9.16, OA-58, ADR-0049)."""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.carts.models import Cart
from apps.inventory.models import InventoryReservation
from apps.orders.models import Order
from tests.factories.inventory import stocked_variant
from tests.factories.orders import cart_with, checkout

pytestmark = pytest.mark.django_db


def test_p9_v23_cart_converted_at_checkout(cart_client, dev_defaults):
    variant = stocked_variant(5)
    cart = cart_with((variant, 2))

    first = checkout(cart_client, cart, idempotency_key="key-1")

    assert first.status_code == 201
    order = Order.objects.get()
    cart.refresh_from_db()
    assert cart.converted_order_id == order.pk

    # A second checkout from the converted cart, with a new key, creates and reserves nothing.
    again = checkout(cart_client, cart, idempotency_key="key-2")
    assert again.status_code == 400
    assert Order.objects.count() == 1
    assert InventoryReservation.objects.count() == 1

    # The same key and body still returns the original order.
    replay = checkout(cart_client, cart, idempotency_key="key-1")
    assert replay.status_code == 200 and replay.json() == first.json()
    assert Order.objects.count() == 1

    # The same key with another body is still refused as a reused key.
    reused = checkout(
        cart_client, cart, idempotency_key="key-1", email="otro@example.com"
    )
    assert reused.status_code == 422

    # The cart endpoints treat the converted cart as gone: the next add makes a fresh cart.
    added = cart_client.post(
        "/api/cart/lines/",
        {"variant_public_id": str(variant.public_id), "quantity": 1},
        format="json",
    )
    assert added.status_code == 201
    fresh = Cart.objects.get(token=cart_client.cookies["cart_token"].value)
    assert fresh.pk != cart.pk and fresh.converted_order_id is None
    assert fresh.lines.count() == 1


def test_p9_v23_a_failed_checkout_leaves_the_cart_open(cart_client, dev_defaults):
    cart = cart_with((stocked_variant(1), 3))

    response = checkout(cart_client, cart)

    assert response.status_code == 409
    cart.refresh_from_db()
    assert cart.converted_order_id is None
    assert not Order.objects.exists()


def test_p9_v23_purge_stale_carts_keeps_a_converted_cart(cart_client, dev_defaults):
    cart = cart_with((stocked_variant(5), 1))
    assert checkout(cart_client, cart).status_code == 201
    Cart.objects.filter(pk=cart.pk).update(
        updated_at=timezone.now() - timedelta(days=90)
    )

    call_command("purge_stale_carts")

    assert Cart.objects.filter(pk=cart.pk).exists()
