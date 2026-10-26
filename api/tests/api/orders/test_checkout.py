"""`POST /api/checkout/` (SPEC.md T8.4): idempotency, price freezing, atomic refusals and
validation."""

import pytest

from apps.inventory.models import InventoryReservation
from apps.orders.models import Order
from tests.factories.inventory import stocked_variant
from tests.factories.orders import CHECKOUT_ADDRESS, cart_with, checkout

pytestmark = pytest.mark.django_db


@pytest.fixture
def checkout_client(cart_client, dev_defaults):
    return cart_client


def test_checkout_creates_the_order_and_returns_the_payment_link(checkout_client):
    variant = stocked_variant(5, price_cents=45000)
    cart = cart_with((variant, 2))

    response = checkout(checkout_client, cart, customer_note="Sin timbre")

    assert response.status_code == 201
    order = Order.objects.get()
    body = response.json()
    assert body["order_number"] == order.number
    assert body["order_public_id"] == str(order.public_id)
    assert "/dev/payments/checkout/" in body["checkout_url"]
    assert order.state == "pending_payment"
    assert order.shipping_address["street"] == CHECKOUT_ADDRESS["street"]
    assert order.customer_note == "Sin timbre"
    assert response["Cache-Control"] == "no-store"


def test_checkout_requires_csrf(checkout_client):
    cart = cart_with((stocked_variant(5), 1))
    checkout_client.drop_csrf()

    response = checkout(checkout_client, cart)

    assert response.status_code == 403
    assert not Order.objects.exists()


def test_p8_v03_idempotent_checkout(checkout_client):
    cart = cart_with((stocked_variant(5), 2))

    first = checkout(checkout_client, cart, idempotency_key="key-1")
    second = checkout(checkout_client, cart, idempotency_key="key-1")

    assert first.status_code == 201 and second.status_code == 200
    assert second.json() == first.json()
    assert Order.objects.count() == 1
    assert InventoryReservation.objects.count() == 1
    order = Order.objects.get()
    assert (order.idempotency_key, order.cart_token) == ("key-1", cart.token)


def test_p8_v03_a_body_in_another_key_order_is_the_same_request(checkout_client):
    cart = cart_with((stocked_variant(5), 1))
    first = checkout(checkout_client, cart, idempotency_key="key-1")

    payload = {
        "customer_note": "",
        "address_payload": dict(reversed(CHECKOUT_ADDRESS.items())),
        "fulfillment_method": "delivery",
        "phone": "5555555555",
        "email": "cliente@example.com",
    }
    second = checkout_client.post(
        "/api/checkout/", payload, format="json", HTTP_IDEMPOTENCY_KEY="key-1"
    )

    assert second.status_code == 200 and second.json() == first.json()


def test_p8_v08_idempotency_key_reused_different_body(checkout_client):
    cart = cart_with((stocked_variant(5), 1))
    first = checkout(checkout_client, cart, idempotency_key="key-1")

    second = checkout(
        checkout_client, cart, idempotency_key="key-1", email="otro@example.com"
    )

    assert second.status_code == 422
    assert second.json()["code"] == "idempotency_key_reused"
    assert Order.objects.count() == 1
    original = Order.objects.get()
    assert original.number == first.json()["order_number"]
    assert original.email == "cliente@example.com"


def test_the_same_key_on_another_cart_is_a_new_order(checkout_client):
    variant = stocked_variant(5)
    first_cart = cart_with((variant, 1))
    second_cart = cart_with((variant, 1))

    first = checkout(checkout_client, first_cart, idempotency_key="key-1")
    second = checkout(checkout_client, second_cart, idempotency_key="key-1")

    assert first.status_code == second.status_code == 201
    assert Order.objects.count() == 2


def test_p8_v09_price_change_between_cart_and_checkout(checkout_client):
    variant = stocked_variant(5, price_cents=10000)
    cart = cart_with((variant, 1))
    checkout_client.cookies["cart_token"] = str(cart.token)
    shown = checkout_client.get("/api/cart/").json()["totals"]["total_cents"]
    variant.price_cents = 12000
    variant.save()

    response = checkout(checkout_client, cart, expected_total_cents=shown)

    # G4, ADR-0042: a mismatch returns 409 with the fresh totals and reserves nothing.
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "total_changed"
    assert body["totals"]["subtotal_cents"] == 12000
    assert body["totals"]["total_cents"] == (
        body["totals"]["subtotal_cents"] + body["totals"]["shipping_cents"]
    )
    assert set(body["totals"]) == {
        "subtotal_cents",
        "shipping_cents",
        "discount_cents",
        "total_cents",
        "tax_included_cents",
    }
    assert not Order.objects.exists()
    assert not InventoryReservation.objects.exists()


def test_p8_v09_a_second_press_with_the_fresh_total_pays_it(checkout_client):
    variant = stocked_variant(5, price_cents=10000)
    cart = cart_with((variant, 1))
    variant.price_cents = 12000
    variant.save()
    refused = checkout(checkout_client, cart, expected_total_cents=10000)
    fresh = refused.json()["totals"]["total_cents"]

    response = checkout(checkout_client, cart, expected_total_cents=fresh)

    assert refused.status_code == 409 and response.status_code == 201
    assert Order.objects.get().total_cents == fresh


def test_p8_v09_a_price_drop_is_refused_too(checkout_client):
    variant = stocked_variant(5, price_cents=10000)
    cart = cart_with((variant, 1))
    variant.price_cents = 8000
    variant.save()

    response = checkout(checkout_client, cart, expected_total_cents=10000)

    assert response.status_code == 409
    assert response.json()["totals"]["subtotal_cents"] == 8000
    assert not Order.objects.exists()
    assert not InventoryReservation.objects.exists()


def test_p8_v09_without_the_field_nothing_is_compared(checkout_client):
    cart = cart_with((stocked_variant(5, price_cents=10000), 1))

    assert checkout(checkout_client, cart).status_code == 201


def test_p8_v09_a_negative_expected_total_is_a_field_error(checkout_client):
    cart = cart_with((stocked_variant(5), 1))

    response = checkout(checkout_client, cart, expected_total_cents=-1)

    assert response.status_code == 400
    assert "expected_total_cents" in response.json()
    assert not Order.objects.exists()


def test_p8_v09_stock_failures_are_checked_before_the_total(checkout_client):
    short = stocked_variant(1, price_cents=10000)
    cart = cart_with((short, 3))

    response = checkout(checkout_client, cart, expected_total_cents=1)

    assert response.status_code == 409
    assert response.json()["code"] == "lines_unavailable"


def test_p8_v09_a_replay_returns_the_order_before_the_comparison(checkout_client):
    variant = stocked_variant(5, price_cents=10000)
    cart = cart_with((variant, 1))
    first = checkout(
        checkout_client, cart, idempotency_key="key-1", expected_total_cents=None
    )
    variant.price_cents = 12000
    variant.save()

    replay = checkout(checkout_client, cart, idempotency_key="key-1")

    assert first.status_code == 201 and replay.status_code == 200
    assert replay.json() == first.json()
    assert Order.objects.count() == 1


def test_p8_v09_the_expected_total_is_part_of_the_fingerprint(checkout_client):
    variant = stocked_variant(5, price_cents=10000)
    cart = cart_with((variant, 1))
    refused = checkout(checkout_client, cart, expected_total_cents=1)
    fresh = refused.json()["totals"]["total_cents"]
    first = checkout(
        checkout_client, cart, idempotency_key="key-1", expected_total_cents=fresh
    )

    other = checkout(
        checkout_client, cart, idempotency_key="key-1", expected_total_cents=fresh + 1
    )

    assert first.status_code == 201
    assert other.status_code == 422
    assert other.json()["code"] == "idempotency_key_reused"


def test_p8_v09_the_order_keeps_the_checkout_time_price(checkout_client):
    variant = stocked_variant(5, price_cents=10000)
    cart = cart_with((variant, 1))
    variant.price_cents = 12000
    variant.save()

    assert checkout(checkout_client, cart).status_code == 201
    variant.price_cents = 15000
    variant.save()

    assert Order.objects.get().lines.get().unit_price_cents == 12000


def test_p8_v10_partial_stock_failure_atomic(checkout_client):
    plenty = stocked_variant(5)
    short = stocked_variant(1)
    cart = cart_with((plenty, 2), (short, 3))

    response = checkout(checkout_client, cart, idempotency_key="key-1")

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "lines_unavailable"
    assert body["line_errors"] == [
        {
            "variant_public_id": str(short.public_id),
            "sku": short.sku,
            "code": "insufficient_stock",
            "requested": 3,
            "available": 1,
        }
    ]
    assert not Order.objects.exists()
    assert not InventoryReservation.objects.exists()


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"email": None}, "email"),
        ({"email": "no-es-un-correo"}, "email"),
        ({"address_payload": None}, "address_payload"),
        (
            {"address_payload": {**CHECKOUT_ADDRESS, "postal_code": "0670"}},
            "address_payload",
        ),
        ({"fulfillment_method": "pickup"}, "fulfillment_method"),
    ],
)
def test_p8_v18_checkout_validation(checkout_client, body, field):
    cart = cart_with((stocked_variant(5), 1))

    response = checkout(checkout_client, cart, **body)

    assert response.status_code == 400
    assert field in response.json()
    assert not Order.objects.exists()
    assert not InventoryReservation.objects.exists()


def test_p8_v18_empty_cart(checkout_client):
    response = checkout(checkout_client, checkout_client.cart)

    assert response.status_code == 400
    assert "cart" in response.json()
    assert not Order.objects.exists()


def test_p8_v18_no_cart_at_all(anonymous_cart_client, dev_defaults):
    response = checkout(anonymous_cart_client)

    assert response.status_code == 400
    assert "cart" in response.json()


def test_p8_v18_a_postal_code_without_a_shipping_price(checkout_client):
    cart = cart_with((stocked_variant(5), 1))

    response = checkout(
        checkout_client,
        cart,
        address_payload={**CHECKOUT_ADDRESS, "postal_code": "00000"},
    )

    assert response.status_code == 400
    assert "postal_code" in response.json()["address_payload"]
    assert not Order.objects.exists()


def test_an_idempotency_key_that_is_too_long_is_refused(checkout_client):
    cart = cart_with((stocked_variant(5), 1))

    response = checkout(checkout_client, cart, idempotency_key="k" * 256)

    assert response.status_code == 400
    assert "idempotency_key" in response.json()
    assert not Order.objects.exists()
