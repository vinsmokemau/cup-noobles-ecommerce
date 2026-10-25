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
