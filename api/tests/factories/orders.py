import factory

from apps.orders.models import Order, OrderLine


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
