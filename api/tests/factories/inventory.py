from datetime import timedelta

import factory

from apps.inventory import services
from apps.inventory.models import InventoryReservation, Location, StockItem, StockLedger
from tests.factories.catalog import VariantFactory
from tests.factories.orders import DraftOrderFactory


class LocationFactory(factory.django.DjangoModelFactory):
    """The warehouse. It is never presented as a store (CR-47)."""

    class Meta:
        model = Location
        django_get_or_create = ("code",)

    code = "almacen"
    name = "Almacén de prueba"
    kind = Location.Kind.WAREHOUSE


class StockItemFactory(factory.django.DjangoModelFactory):
    """An empty stock row. Put units on the shelf through `stocked_variant` or `receive_stock`,
    so the ledger agrees with `on_hand`."""

    class Meta:
        model = StockItem

    variant = factory.SubFactory(VariantFactory)
    location = factory.SubFactory(LocationFactory)


def stocked_variant(on_hand, safety_stock=0, location=None, **variant_fields):
    """A variant with `on_hand` units received into `location` (the warehouse by default)."""
    location = location or LocationFactory()
    variant = VariantFactory(**variant_fields)
    StockItemFactory(variant=variant, location=location, safety_stock=safety_stock)
    if on_hand:
        services.receive_stock(variant, location, on_hand)
    return variant


def holding_order(variant, qty, ttl=timedelta(hours=1)):
    """A draft order with a `held` reservation of `qty`, built through `reserve()`."""
    order = DraftOrderFactory()
    services.reserve(order, [(variant, qty)], ttl=ttl)
    return order


def assert_stock_integrity(variant):
    """CR-04 and CR-05 for every stock row of `variant`: `0 <= reserved <= on_hand`, the ledger
    sums to `on_hand`, and `reserved` equals the units in `held` stock reservations."""
    for item in StockItem.objects.filter(variant=variant):
        ledger = sum(
            StockLedger.objects.filter(stock_item=item).values_list("delta", flat=True)
        )
        held = sum(
            InventoryReservation.objects.filter(
                variant=variant,
                location=item.location,
                kind=InventoryReservation.Kind.STOCK,
                state=InventoryReservation.State.HELD,
            ).values_list("quantity", flat=True)
        )
        assert 0 <= item.reserved <= item.on_hand, (
            f"{variant.sku}: {item.reserved=} {item.on_hand=}"
        )
        assert ledger == item.on_hand, (
            f"{variant.sku}: ledger {ledger} != on_hand {item.on_hand}"
        )
        assert held == item.reserved, (
            f"{variant.sku}: held {held} != reserved {item.reserved}"
        )
