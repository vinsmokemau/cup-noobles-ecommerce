from datetime import timedelta

import pytest
from django.core.management import call_command

from apps.inventory import services
from apps.inventory.errors import InsufficientStock
from apps.inventory.models import InventoryReservation, StockItem, StockLedger
from apps.orders.models import Order
from tests.factories.inventory import (
    assert_stock_integrity,
    holding_order,
    stocked_variant,
)
from tests.factories.orders import DraftOrderFactory

pytestmark = pytest.mark.django_db

TTL = timedelta(hours=1)


def stock_of(variant):
    return StockItem.objects.get(variant=variant)


def test_p4_v02_commit_moves_stock_and_writes_ledger():
    variant = stocked_variant(on_hand=5)
    order = holding_order(variant, 2)

    services.commit_reservations(order)

    item = stock_of(variant)
    assert (item.on_hand, item.reserved) == (3, 0)
    sale = StockLedger.objects.get(stock_item=item, reason="sale_online")
    assert (sale.delta, sale.balance_after, sale.order_id) == (-2, 3, order.pk)
    assert InventoryReservation.objects.get(order=order).state == "committed"
    assert_stock_integrity(variant)


def test_p4_v05_release_idempotent():
    variant = stocked_variant(on_hand=5)
    order = holding_order(variant, 2)

    services.release_reservations(order, reason="cancelled")
    services.release_reservations(order, reason="cancelled")

    item = stock_of(variant)
    assert (item.on_hand, item.reserved) == (5, 0)
    assert InventoryReservation.objects.get(order=order).state == "released"
    assert not StockLedger.objects.filter(
        stock_item=item, reason="sale_online"
    ).exists()
    assert_stock_integrity(variant)


def test_p4_v09_reserve_all_or_nothing():
    plenty = stocked_variant(on_hand=5)
    short = stocked_variant(on_hand=1)
    order = DraftOrderFactory()

    with pytest.raises(InsufficientStock) as raised:
        services.reserve(order, [(plenty, 2), (short, 2)], ttl=TTL)

    assert raised.value.variant == short
    assert (raised.value.requested, raised.value.available) == (2, 1)
    assert stock_of(plenty).reserved == 0
    assert stock_of(short).reserved == 0
    assert not InventoryReservation.objects.filter(order=order).exists()


def test_p4_v11_safety_stock_respected():
    variant = stocked_variant(on_hand=5, safety_stock=2)

    with pytest.raises(InsufficientStock) as raised:
        services.reserve(DraftOrderFactory(), [(variant, 4)], ttl=TTL)
    assert raised.value.available == 3

    services.reserve(DraftOrderFactory(), [(variant, 3)], ttl=TTL)
    assert stock_of(variant).reserved == 3


def test_reserve_sets_the_expiry_from_the_ttl(clock):
    clock.travel("2026-03-01T12:00:00Z")
    variant = stocked_variant(on_hand=2)

    [reservation] = services.reserve(
        DraftOrderFactory(), [(variant, 1)], ttl=timedelta(hours=4)
    )

    assert reservation.expires_at.isoformat() == "2026-03-01T16:00:00+00:00"
    assert reservation.state == "held"


def test_reserve_adds_up_repeated_lines_of_one_variant():
    variant = stocked_variant(on_hand=3)

    with pytest.raises(InsufficientStock) as raised:
        services.reserve(DraftOrderFactory(), [(variant, 2), (variant, 2)], ttl=TTL)
    assert raised.value.requested == 4

    [reservation] = services.reserve(
        DraftOrderFactory(), [(variant, 1), (variant, 2)], ttl=TTL
    )
    assert reservation.quantity == 3


def test_reserve_without_lines_does_nothing():
    assert services.reserve(DraftOrderFactory(), [], ttl=TTL) == []


def test_a_variant_with_no_stock_row_has_none_available():
    variant = stocked_variant(on_hand=0)
    StockItem.objects.filter(variant=variant).delete()

    with pytest.raises(InsufficientStock) as raised:
        services.reserve(DraftOrderFactory(), [(variant, 1)], ttl=TTL)
    assert raised.value.available == 0


def test_p4_v16_commit_twice():
    # G15's proposed resolution: the second call is a no-op. `commit_reservations` already
    # behaves that way, so the test passes and carries no xfail (see the task report).
    variant = stocked_variant(on_hand=5)
    order = holding_order(variant, 2)

    services.commit_reservations(order)
    services.commit_reservations(order)

    item = stock_of(variant)
    assert (item.on_hand, item.reserved) == (3, 0)
    assert (
        StockLedger.objects.filter(stock_item=item, reason="sale_online").count() == 1
    )
    assert_stock_integrity(variant)


def test_a_released_hold_is_not_committed_afterwards():
    variant = stocked_variant(on_hand=5)
    order = holding_order(variant, 2)

    services.release_reservations(order, reason="expired")
    services.commit_reservations(order)

    assert stock_of(variant).on_hand == 5
    assert InventoryReservation.objects.get(order=order).state == "released"


def expired_hold(clock, on_hand=5, qty=2):
    clock.travel("2026-03-01T12:00:00Z")
    variant = stocked_variant(on_hand=on_hand)
    return variant, holding_order(variant, qty, ttl=timedelta(hours=1))


@pytest.mark.xfail(
    strict=True,
    reason="G37: the order moves to expired through apply_event, which arrives in Phase 8",
)
def test_p4_v03_expired_hold_leaves_no_ledger(clock):
    variant, order = expired_hold(clock)
    ledger_rows = StockLedger.objects.count()
    clock.travel("2026-03-01T13:00:01Z")

    call_command("expire_reservations")

    item = stock_of(variant)
    assert (item.on_hand, item.reserved) == (5, 0)
    assert StockLedger.objects.count() == ledger_rows
    assert InventoryReservation.objects.get(order=order).state == "released"
    order.refresh_from_db()
    assert order.state == "expired"


def test_p4_v03_the_hold_is_released_without_a_ledger_row(clock):
    # What P4-V03 asserts today; its order-state line waits for apply_event (G37).
    variant, order = expired_hold(clock)
    ledger_rows = StockLedger.objects.count()
    clock.travel("2026-03-01T13:00:01Z")

    call_command("expire_reservations")
    call_command("expire_reservations")

    item = stock_of(variant)
    assert (item.on_hand, item.reserved) == (5, 0)
    assert StockLedger.objects.count() == ledger_rows
    reservation = InventoryReservation.objects.get(order=order)
    assert reservation.state == "released"
    assert reservation.settled_at is not None
    assert_stock_integrity(variant)


def test_p4_v08_ttl_boundary(clock):
    variant, order = expired_hold(clock)

    clock.travel("2026-03-01T13:00:00Z")
    call_command("expire_reservations")
    assert InventoryReservation.objects.get(order=order).state == "held"
    assert stock_of(variant).reserved == 2

    clock.travel("2026-03-01T13:00:00.000001Z")
    call_command("expire_reservations")
    assert InventoryReservation.objects.get(order=order).state == "released"
    assert stock_of(variant).reserved == 0


def test_expiry_leaves_unlapsed_and_settled_holds_alone(clock):
    variant, lapsing = expired_hold(clock, on_hand=6, qty=1)
    paid = holding_order(variant, 2)
    services.commit_reservations(paid)
    later = holding_order(variant, 1, ttl=timedelta(hours=3))
    clock.travel("2026-03-01T13:30:00Z")

    call_command("expire_reservations")

    states = {
        r.order_id: r.state
        for r in InventoryReservation.objects.filter(variant=variant)
    }
    assert states == {
        lapsing.pk: "released",
        paid.pk: "committed",
        later.pk: "held",
    }
    assert_stock_integrity(variant)


def test_expiry_leaves_the_holds_of_a_paid_order_to_its_own_settlement(clock):
    variant, order = expired_hold(clock)
    Order.objects.filter(pk=order.pk).update(state="paid", shipping_address={})
    clock.travel("2026-03-01T14:00:00Z")

    call_command("expire_reservations")

    assert InventoryReservation.objects.get(order=order).state == "held"
