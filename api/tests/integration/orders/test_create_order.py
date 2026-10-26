"""`create_order_from_cart` (SPEC.md T8.2): what it freezes, what it refuses, and that a
refusal leaves nothing behind."""

import re
from datetime import timedelta

import pytest
from django.conf import settings
from django.utils import timezone

from apps.carts.models import Cart
from apps.inventory.models import InventoryReservation, StockItem
from apps.orders.models import Order, OrderEvent, OrderLine
from apps.orders.services import (
    EmptyCart,
    LinesUnavailable,
    ShippingUnavailable,
    UnsupportedFulfillment,
)
from apps.payments.models import Payment
from tests.factories.catalog import ProductFactory, ProductImageFactory, VariantFactory
from tests.factories.inventory import assert_stock_integrity, stocked_variant
from tests.factories.orders import STAND_IN_ADDRESS, cart_with, place_order

pytestmark = pytest.mark.django_db


def test_creates_pending_payment_order_with_frozen_lines(dev_defaults):
    product = ProductFactory(name="Nendoroid Link")
    variant = stocked_variant(5, product=product, price_cents=45000, options={"c": "x"})
    ProductImageFactory(product=product, storage_key="products/link.jpg")
    order = place_order(
        cart_with((variant, 2)), phone="5555555555", customer_note="Sin timbre"
    )

    assert order.state == "pending_payment"
    assert re.fullmatch(r"CN-\d{4}-\d{6}", order.number)
    assert (order.email, order.phone, order.customer_note) == (
        "cliente@example.com",
        "5555555555",
        "Sin timbre",
    )
    assert order.shipping_address == STAND_IN_ADDRESS
    assert (order.has_preorder_items, order.earliest_release_date) == (False, None)
    line = order.lines.get()
    assert (line.sku, line.product_name, line.options_snapshot, line.image_key) == (
        variant.sku,
        "Nendoroid Link",
        {"c": "x"},
        "products/link.jpg",
    )
    assert (line.quantity, line.unit_price_cents, line.line_total_cents) == (
        2,
        45000,
        90000,
    )
    assert order.subtotal_cents == 90000
    assert order.total_cents == order.subtotal_cents + order.shipping_cents
    assert order.shipping_cents > 0 and order.shipping_rate_name

    # Later catalog changes never alter the order (CR-03).
    variant.price_cents = 1
    variant.save()
    assert OrderLine.objects.get(pk=line.pk).unit_price_cents == 45000


def test_checkout_submitted_reserves_and_opens_the_payment(dev_defaults):
    variant = stocked_variant(5)
    before = timezone.now()
    order = place_order(cart_with((variant, 3)))

    reservation = InventoryReservation.objects.get(order=order)
    assert (reservation.state, reservation.quantity) == ("held", 3)
    assert StockItem.objects.get(variant=variant).reserved == 3
    ttl = timedelta(minutes=settings.RESERVATION_TTL_CARD_MINUTES)
    assert order.payment_deadline_at == pytest.approx(
        order.placed_at + ttl, abs=timedelta(seconds=1)
    )
    assert order.placed_at >= before
    event = OrderEvent.objects.get(order=order)
    assert (event.from_state, event.to_state, event.event) == (
        "draft",
        "pending_payment",
        "checkout_submitted",
    )
    payment = Payment.objects.get(order=order)
    assert payment.raw["checkout_url"].startswith(settings.SITE_URL)
    assert_stock_integrity(variant)


def test_order_numbers_are_distinct(dev_defaults):
    variant = stocked_variant(5)
    first = place_order(cart_with((variant, 1)))
    second = place_order(cart_with((variant, 1)))
    assert first.number != second.number


def test_every_failing_line_is_reported_and_nothing_is_created(dev_defaults):
    plenty = stocked_variant(5)
    short = stocked_variant(1)
    gone = stocked_variant(5, is_active=False)
    cart = cart_with((plenty, 1), (short, 3), (gone, 1))

    with pytest.raises(LinesUnavailable) as raised:
        place_order(cart)

    by_sku = {error.sku: error for error in raised.value.line_errors}
    assert set(by_sku) == {short.sku, gone.sku}
    assert (by_sku[short.sku].code, by_sku[short.sku].requested) == (
        "insufficient_stock",
        3,
    )
    assert by_sku[short.sku].available == 1
    assert by_sku[gone.sku].code == "unavailable"
    assert not Order.objects.exists()
    assert not InventoryReservation.objects.exists()
    assert StockItem.objects.get(variant=plenty).reserved == 0


def test_empty_cart_is_refused(dev_defaults):
    with pytest.raises(EmptyCart):
        place_order(cart_with())
    assert not Order.objects.exists()


def test_unknown_postal_code_is_refused_without_an_order(dev_defaults):
    cart = cart_with((stocked_variant(2), 1))
    with pytest.raises(ShippingUnavailable):
        place_order(cart, address_or_location={"postal_code": "00000"})
    assert not Order.objects.exists()
    assert not InventoryReservation.objects.exists()


def test_pickup_is_release_2(dev_defaults):
    cart = cart_with((stocked_variant(2), 1))
    with pytest.raises(UnsupportedFulfillment):
        place_order(cart, fulfillment_method="pickup")
    assert not Order.objects.exists()


def test_same_variant_in_two_lines_is_checked_together(dev_defaults):
    variant = VariantFactory()
    cart = cart_with((variant, 1))
    assert cart.lines.count() == 1  # one line per variant (cart_line unique key)
    stocked = stocked_variant(2)
    order = place_order(cart_with((stocked, 2)))
    assert order.lines.get().quantity == 2


def test_a_cart_converted_meanwhile_is_refused_even_for_a_stale_caller(dev_defaults):
    cart = cart_with((stocked_variant(5), 1))
    earlier = place_order(cart_with((stocked_variant(5), 1)))
    Cart.objects.filter(pk=cart.pk).update(converted_order=earlier)

    with pytest.raises(EmptyCart):
        place_order(cart)

    assert Order.objects.count() == 1
