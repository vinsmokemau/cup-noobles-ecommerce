"""P7-V10, P7-V02, P7-V11: cart line bounds, availability and the line endpoints (T7.1, T7.4)."""

import uuid

import pytest

from apps.carts.models import Cart, CartLine
from apps.catalog.models import Product
from tests.factories.carts import CartLineFactory
from tests.factories.catalog import VariantFactory
from tests.factories.inventory import holding_order, stocked_variant

pytestmark = pytest.mark.django_db

LINES = "/api/cart/lines/"


def add(client, variant, quantity):
    return client.post(
        LINES,
        {"variant_public_id": str(variant.public_id), "quantity": quantity},
        format="json",
    )


@pytest.mark.parametrize("quantity", [0, 100, -1])
def test_p7_v10_quantity_bounds(cart_client, quantity):
    variant = VariantFactory()

    response = add(cart_client, variant, quantity)

    assert response.status_code == 400
    assert "quantity" in response.json()
    assert not CartLine.objects.exists()


def test_p7_v10_quantity_bounds_accept_99(cart_client):
    variant = VariantFactory()

    response = add(cart_client, variant, 99)

    assert response.status_code == 201
    assert response.json()["lines"][0]["quantity"] == 99
    assert CartLine.objects.get().quantity == 99


@pytest.mark.parametrize("quantity", [0, 100])
def test_p7_v10_patch_quantity_bounds(cart_client, quantity):
    line = CartLineFactory(cart=cart_client.cart, quantity=2)

    response = cart_client.patch(
        f"{LINES}{line.pk}/", {"quantity": quantity}, format="json"
    )

    assert response.status_code == 400
    line.refresh_from_db()
    assert line.quantity == 2


def test_patch_accepts_99(cart_client):
    line = CartLineFactory(cart=cart_client.cart, quantity=2)

    response = cart_client.patch(f"{LINES}{line.pk}/", {"quantity": 99}, format="json")

    assert response.status_code == 200
    line.refresh_from_db()
    assert line.quantity == 99


def test_first_write_creates_a_cart_and_sets_the_cookie(anonymous_cart_client):
    variant = VariantFactory()
    assert "cart_token" not in anonymous_cart_client.cookies

    response = add(anonymous_cart_client, variant, 2)

    assert response.status_code == 201
    cookie = response.cookies["cart_token"]
    assert cookie["httponly"]
    assert cookie["samesite"] == "Lax"
    assert cookie["max-age"] == 60 * 60 * 24 * 30
    follow_up = anonymous_cart_client.get("/api/cart/")
    assert [line["quantity"] for line in follow_up.json()["lines"]] == [2]


def test_get_without_a_token_is_empty_and_creates_nothing(anonymous_cart_client):
    response = anonymous_cart_client.get("/api/cart/")

    assert response.status_code == 200
    body = response.json()
    assert body["fulfillment_method"] is None
    assert body["lines"] == []
    assert body["totals"]["total_cents"] == 0
    assert response["Cache-Control"] == "no-store"
    assert not Cart.objects.exists()


def test_post_upserts_the_same_variant(cart_client):
    variant = VariantFactory()

    first = add(cart_client, variant, 1)
    second = add(cart_client, variant, 4)

    assert (first.status_code, second.status_code) == (201, 200)
    assert [line["quantity"] for line in second.json()["lines"]] == [4]
    assert CartLine.objects.count() == 1


def test_unknown_variant_is_a_400(cart_client):
    response = cart_client.post(
        LINES, {"variant_public_id": str(uuid.uuid4()), "quantity": 1}, format="json"
    )

    assert response.status_code == 400
    assert "variant_public_id" in response.json()


def test_delete_removes_the_line(cart_client):
    line = CartLineFactory(cart=cart_client.cart)

    response = cart_client.delete(f"{LINES}{line.pk}/")

    assert response.status_code == 200
    assert response.json()["lines"] == []
    assert not CartLine.objects.exists()


def test_line_changes_touch_the_cart(cart_client, clock):
    line = CartLineFactory(cart=cart_client.cart)
    cart_client.cart.refresh_from_db()
    before = cart_client.cart.updated_at

    clock.travel("2030-01-01T12:00:00Z")
    cart_client.patch(f"{LINES}{line.pk}/", {"quantity": 3}, format="json")

    cart_client.cart.refresh_from_db()
    assert cart_client.cart.updated_at > before


def test_fulfillment_accepts_delivery_only_in_r1(cart_client, dev_defaults):
    ok = cart_client.post(
        "/api/cart/fulfillment/",
        {"method": "delivery", "postal_code": "06700"},
        format="json",
    )
    pickup = cart_client.post(
        "/api/cart/fulfillment/",
        {"method": "pickup", "pickup_location_id": 1},
        format="json",
    )
    bad_cp = cart_client.post(
        "/api/cart/fulfillment/",
        {"method": "delivery", "postal_code": "6700"},
        format="json",
    )

    assert ok.status_code == 200
    assert ok.json()["fulfillment_method"] == "delivery"
    assert pickup.status_code == 400
    assert "method" in pickup.json()
    assert bad_cp.status_code == 400
    assert "postal_code" in bad_cp.json()


def test_p7_v02_reduced_not_mutated(cart_client):
    variant = stocked_variant(on_hand=2)
    line = CartLineFactory(cart=cart_client.cart, variant=variant, quantity=3)

    body = cart_client.get("/api/cart/").json()

    assert body["lines"][0]["availability"] == "reduced"
    assert body["lines"][0]["max_available"] == 2
    assert body["lines"][0]["quantity"] == 3
    line.refresh_from_db()
    assert line.quantity == 3


def test_availability_ok_and_unavailable_lines(cart_client):
    CartLineFactory(
        cart=cart_client.cart, variant=stocked_variant(on_hand=5), quantity=5
    )
    CartLineFactory(
        cart=cart_client.cart, variant=stocked_variant(on_hand=0), quantity=1
    )

    lines = cart_client.get("/api/cart/").json()["lines"]

    assert [(row["availability"], row["max_available"]) for row in lines] == [
        ("ok", None),
        ("unavailable", None),
    ]


def test_availability_counts_reservations_and_safety_stock(cart_client):
    held = stocked_variant(on_hand=8, safety_stock=2)
    holding_order(held, 3)
    CartLineFactory(cart=cart_client.cart, variant=held, quantity=4)

    line = cart_client.get("/api/cart/").json()["lines"][0]

    assert (line["availability"], line["max_available"]) == ("reduced", 3)


def test_p7_v11_inactive_or_archived_variant(cart_client):
    inactive = stocked_variant(on_hand=5, is_active=False)
    archived = stocked_variant(on_hand=5)
    archived.product.status = Product.Status.ARCHIVED
    archived.product.save(update_fields=["status"])

    for variant in (inactive, archived):
        response = add(cart_client, variant, 1)
        assert response.status_code == 400
        assert "variant_public_id" in response.json()
    assert not CartLine.objects.exists()

    # A line added while the variant was sellable is reported, not removed.
    CartLineFactory(cart=cart_client.cart, variant=inactive, quantity=1)
    CartLineFactory(cart=cart_client.cart, variant=archived, quantity=1)
    lines = cart_client.get("/api/cart/").json()["lines"]
    assert [row["availability"] for row in lines] == ["unavailable", "unavailable"]
    assert CartLine.objects.count() == 2
