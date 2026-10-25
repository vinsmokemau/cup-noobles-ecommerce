"""Inventory services: the only code that changes `on_hand` or `reserved` (CR-05, CR-06).

Every mutation locks the `stock_item` row with `SELECT ... FOR UPDATE` first (CR-07), and every
change to `on_hand` writes a `stock_ledger` row in the same transaction (CR-05). Statements that
lock several rows lock them in primary-key order, so two multi-line calls cannot deadlock.
Pre-order reservations are Release 2 and are not touched here (CR-08).
"""

import logging
from collections.abc import Iterable
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Variant
from apps.inventory.errors import (
    AdjustmentBelowReserved,
    InsufficientStock,
    InvalidQuantity,
)
from apps.inventory.models import (
    InventoryReservation,
    Location,
    StockItem,
    StockLedger,
)
from apps.orders.models import Order

logger = logging.getLogger(__name__)

ADJUSTMENT_REASONS = frozenset(
    {
        StockLedger.Reason.ADJUSTMENT,
        StockLedger.Reason.DAMAGE,
        StockLedger.Reason.COUNT_CORRECTION,
    }
)


def _require_positive(quantity: int) -> None:
    if not isinstance(quantity, int) or quantity < 1:
        raise InvalidQuantity(
            f"Quantity must be a positive whole number, got {quantity!r}"
        )


def _lock_item(variant: Variant, location: Location) -> StockItem:
    """The (variant, location) row, created if missing, locked FOR UPDATE."""
    StockItem.objects.get_or_create(variant=variant, location=location)
    return StockItem.objects.select_for_update().get(variant=variant, location=location)


def _lock_items(ids: Iterable[int]) -> dict[int, StockItem]:
    items = StockItem.objects.select_for_update().filter(pk__in=set(ids)).order_by("pk")
    return {item.pk: item for item in items}


def _write_ledger(
    item: StockItem,
    delta: int,
    reason: str,
    *,
    order: Order | None = None,
    actor=None,
    note: str = "",
) -> None:
    StockLedger.objects.create(
        stock_item=item,
        delta=delta,
        balance_after=item.on_hand,
        reason=reason,
        order=order,
        actor_user_id=actor.pk if actor is not None else None,
        note=note,
    )


def _save(item: StockItem) -> None:
    item.save(update_fields=["on_hand", "reserved", "updated_at"])


def _available(item: StockItem) -> int:
    return max(0, item.on_hand - item.reserved - item.safety_stock)


def receive_stock(variant, location, qty, *, actor=None, note="") -> StockItem:
    """Goods received. on_hand += qty, ledger reason='receipt'."""
    _require_positive(qty)
    return _receive_stock(variant, location, qty, actor, note)


@transaction.atomic
def _receive_stock(variant, location, qty, actor, note) -> StockItem:
    item = _lock_item(variant, location)
    item.on_hand += qty
    _save(item)
    _write_ledger(item, qty, StockLedger.Reason.RECEIPT, actor=actor, note=note)
    return item


def reserve(
    order, lines: list[tuple[Variant, int]], *, ttl: timedelta
) -> list[InventoryReservation]:
    """Hold units for an order. Locks each stock_item FOR UPDATE, checks
    available >= qty, increments reserved, creates a 'held' reservation.
    Raises InsufficientStock(variant, requested, available) — never partially
    reserves. All or nothing.

    Lines for the same variant are added together. Each variant is held from the first active
    fulfillment location whose available units cover the whole quantity.
    """
    for _, quantity in lines:
        _require_positive(quantity)
    return _reserve(order, lines, ttl)


@transaction.atomic
def _reserve(order, lines, ttl) -> list[InventoryReservation]:
    wanted: dict[int, tuple[Variant, int]] = {}
    for variant, quantity in lines:
        _, total = wanted.get(variant.pk, (variant, 0))
        wanted[variant.pk] = (variant, total + quantity)
    if not wanted:
        return []

    candidates = (
        StockItem.objects.filter(
            variant_id__in=wanted,
            location__is_active=True,
            location__is_fulfillment_source=True,
        )
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    items = _lock_items(candidates)

    chosen: list[tuple[StockItem, int]] = []
    for variant, quantity in wanted.values():
        options = [item for item in items.values() if item.variant_id == variant.pk]
        item = next((o for o in options if _available(o) >= quantity), None)
        if item is None:
            raise InsufficientStock(
                variant, quantity, max((_available(o) for o in options), default=0)
            )
        chosen.append((item, quantity))

    expires_at = timezone.now() + ttl
    reservations = []
    for item, quantity in chosen:
        item.reserved += quantity
        _save(item)
        reservations.append(
            InventoryReservation.objects.create(
                order=order,
                variant_id=item.variant_id,
                location_id=item.location_id,
                kind=InventoryReservation.Kind.STOCK,
                quantity=quantity,
                state=InventoryReservation.State.HELD,
                expires_at=expires_at,
            )
        )
    return reservations


def _lock_held(order) -> tuple[dict[int, StockItem], list[InventoryReservation]]:
    """Lock the stock items of the order's held reservations, then the reservations.

    The reservations are read after the stock locks are taken, so a second caller that waited on
    the lock sees them already settled.
    """
    pending = InventoryReservation.objects.filter(
        order=order,
        kind=InventoryReservation.Kind.STOCK,
        state=InventoryReservation.State.HELD,
    )
    item_ids = StockItem.objects.filter(
        variant_id__in=pending.values("variant_id"),
        location_id__in=pending.values("location_id"),
    ).values_list("pk", flat=True)
    items = _lock_items(item_ids)
    held = list(pending.select_for_update().order_by("pk"))
    return items, held


def _item_for(
    items: dict[int, StockItem], reservation: InventoryReservation
) -> StockItem:
    return next(
        item
        for item in items.values()
        if item.variant_id == reservation.variant_id
        and item.location_id == reservation.location_id
    )


@transaction.atomic
def commit_reservations(order) -> None:
    """Payment settled. For each 'held' reservation of kind='stock':
    on_hand -= qty, reserved -= qty, ledger reason='sale_online',
    state -> 'committed'. A second call finds nothing held and changes nothing (G15).
    Pre-order reservations (R2) are not handled yet.
    """
    items, held = _lock_held(order)
    now = timezone.now()
    for reservation in held:
        item = _item_for(items, reservation)
        item.on_hand -= reservation.quantity
        item.reserved -= reservation.quantity
        _save(item)
        _write_ledger(
            item,
            -reservation.quantity,
            StockLedger.Reason.SALE_ONLINE,
            order=order,
        )
        reservation.state = InventoryReservation.State.COMMITTED
        reservation.settled_at = now
        reservation.save(update_fields=["state", "settled_at"])


@transaction.atomic
def release_reservations(order, *, reason: str) -> None:
    """Order cancelled or expired. reserved -= qty for 'stock' kind;
    state -> 'released'. No ledger row: `on_hand` did not move.
    Idempotent: releasing an already-released reservation is a no-op.
    """
    items, held = _lock_held(order)
    now = timezone.now()
    for reservation in held:
        item = _item_for(items, reservation)
        item.reserved -= reservation.quantity
        _save(item)
        reservation.state = InventoryReservation.State.RELEASED
        reservation.settled_at = now
        reservation.save(update_fields=["state", "settled_at"])
    if held:
        logger.info(
            "Released %d reservations of order %s: %s", len(held), order.pk, reason
        )


def adjust_stock(variant, location, delta, *, reason, actor, note) -> None:
    """Manual correction, damage, count. Rejects a delta that would push
    on_hand below reserved."""
    if not isinstance(delta, int) or delta == 0:
        raise InvalidQuantity(
            f"An adjustment must be a non-zero whole number, got {delta!r}"
        )
    if reason not in ADJUSTMENT_REASONS:
        raise ValueError(f"Unknown adjustment reason {reason!r}")
    _adjust_stock(variant, location, delta, reason, actor, note)


@transaction.atomic
def _adjust_stock(variant, location, delta, reason, actor, note) -> None:
    item = _lock_item(variant, location)
    if item.on_hand + delta < item.reserved:
        raise AdjustmentBelowReserved(variant, delta, item.on_hand, item.reserved)
    item.on_hand += delta
    _save(item)
    _write_ledger(item, delta, reason, actor=actor, note=note)
