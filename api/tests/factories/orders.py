import factory

from apps.orders.models import Order, OrderLine, Shipment


class OrderFactory(factory.django.DjangoModelFactory):
    """A `draft` delivery order with a zero total; override the totals and state per test."""

    class Meta:
        model = Order

    number = factory.Sequence(lambda n: f"CN-2026-{n:06d}")
    email = factory.Sequence(lambda n: f"pedido{n}@example.com")
    state = "draft"
    fulfillment_method = "delivery"
    subtotal_cents = 0
    total_cents = 0


class DraftOrderFactory(OrderFactory):
    """A `draft` order only. State traits arrive in Phase 8 through `order_in_state`."""


class OrderLineFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OrderLine

    order = factory.SubFactory(OrderFactory)
    sku = factory.Sequence(lambda n: f"SKU-{n}")
    product_name = factory.Sequence(lambda n: f"Producto {n}")
    quantity = 1
    unit_price_cents = 10000
    line_total_cents = factory.LazyAttribute(
        lambda line: line.unit_price_cents * line.quantity
    )


class ShipmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Shipment

    order = factory.SubFactory(OrderFactory)
    carrier = "manual"
    tracking_number = factory.Sequence(lambda n: f"GUIA{n:06d}")


STAND_IN_ADDRESS = {"street": "Calle de prueba 1", "postal_code": "06700"}


def order_in_state(state, **fields):
    """An order stored directly in `state`, with a complete delivery target and a total of
    10000. Tests start here instead of walking the machine; only the machine moves a real
    order."""
    fields.setdefault("shipping_address", STAND_IN_ADDRESS)
    fields.setdefault("subtotal_cents", 10000)
    fields.setdefault("total_cents", 10000)
    return OrderFactory(state=state, **fields)


def cart_with(*lines, fulfillment_method="delivery"):
    """A cart holding `(variant, quantity)` pairs, in the order given."""
    from tests.factories.carts import CartFactory, CartLineFactory

    cart = CartFactory(fulfillment_method=fulfillment_method)
    for variant, quantity in lines:
        CartLineFactory(cart=cart, variant=variant, quantity=quantity)
    return cart


def place_order(cart, **fields):
    """Checkout through `create_order_from_cart` (T8.2): a real `pending_payment` order.
    Needs the `dev_defaults` fixture, which seeds the shipping zones and postal codes."""
    from apps.orders.services import create_order_from_cart

    fields.setdefault("email", "cliente@example.com")
    fields.setdefault("fulfillment_method", "delivery")
    fields.setdefault("address_or_location", STAND_IN_ADDRESS)
    return create_order_from_cart(cart, **fields)


def order_through_checkout(state, *, quantity=2, stock=10):
    """An order that reaches `state` only through a real checkout and `apply_event`, so it
    cannot be an impossible order. Supports the delivery path up to `completed`."""
    from apps.orders.state_machine import apply_event
    from tests.factories.inventory import stocked_variant

    order = place_order(cart_with((stocked_variant(stock), quantity)))
    path = [
        ("paid", "payment_approved", lambda o: {"amount_cents": o.total_cents}),
        ("preparing", "auto", lambda o: {}),
        ("shipped", "shipment_created", lambda o: _with_shipment(o)),
        ("delivered", "marked_delivered", lambda o: {}),
        ("completed", "auto_after_7d", lambda o: {}),
    ]
    if state == "pending_payment":
        return order
    for _target, event, kwargs in path:
        order = apply_event(order.pk, event, **kwargs(order))
        if order.state == state:
            return order
    raise ValueError(f"No checkout path reaches {state!r}")


def _with_shipment(order):
    ShipmentFactory(order=order)
    return {}
