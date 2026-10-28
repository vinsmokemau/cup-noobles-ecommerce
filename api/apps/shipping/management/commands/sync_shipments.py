"""Move shipped orders to `delivered` when the carrier says so (SPEC.md 10.11, §4.8, REQ-022).

For each shipment of a `shipped` order with no `delivered_at`, ask the active carrier for its
status:

- `DELIVERED`: set `delivered_at` and fire T11 (`marked_delivered`, actor `carrier`).
- `EXCEPTION`: log an error and report it in the run summary; no transition.
- `IN_TRANSIT` or `UNKNOWN`: nothing.

A delivered shipment is never selected again, so a later report cannot regress it and a second
run is a no-op. Each delivery runs in one transaction that locks the order first (the same lock
order as `apply_event`), so staff firing T11 at the same moment, or an overlapping run, moves the
order once: the loser finds the shipment delivered or the order no longer `shipped`, and skips.
"""

import logging
from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.core import providers
from apps.orders.models import Order, Shipment
from apps.orders.state_machine import IllegalTransition, apply_event
from apps.shipping.carriers.base import ShipmentStatus

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    checked: int = 0
    delivered: int = 0
    failed: int = 0
    exceptions: list[str] = field(default_factory=list)


def _pending_shipments(shipment_ids: Collection[int] | None) -> list[Shipment]:
    pending = Shipment.objects.filter(order__state="shipped", delivered_at__isnull=True)
    if shipment_ids is not None:
        pending = pending.filter(pk__in=shipment_ids)
    return list(pending.select_related("order").order_by("pk"))


def _mark_delivered(shipment_id: int, order_id: int) -> bool:
    """T11 for one shipment. False when someone else got there first."""
    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order_id)
            shipment = Shipment.objects.get(pk=shipment_id)
            if order.state != "shipped" or shipment.delivered_at is not None:
                return False
            shipment.delivered_at = timezone.now()
            shipment.save(update_fields=["delivered_at"])
            apply_event(order, "marked_delivered", actor="carrier")
    except IllegalTransition:
        return False
    return True


def sync_shipments(shipment_ids: Collection[int] | None = None) -> SyncResult:
    """Sync every pending shipment, or only those in `shipment_ids` (the mock tracking page)."""
    carrier = providers.carrier()
    result = SyncResult()
    for shipment in _pending_shipments(shipment_ids):
        result.checked += 1
        try:
            status = carrier.get_status(shipment.tracking_number)
            if status is ShipmentStatus.DELIVERED:
                if _mark_delivered(shipment.pk, shipment.order_id):
                    result.delivered += 1
            elif status is ShipmentStatus.EXCEPTION:
                result.exceptions.append(shipment.tracking_number)
                logger.error(
                    "Carrier reports an exception for shipment %s of order %s",
                    shipment.tracking_number,
                    shipment.order.number,
                )
        except Exception:  # noqa: BLE001 - one shipment's failure must not stop the others
            result.failed += 1
            logger.exception(
                "sync_shipments failed for shipment %s", shipment.tracking_number
            )
    return result


class Command(BaseCommand):
    help = "Sync shipment status from the carrier and mark delivered orders (SPEC.md 10.11, T11)."

    def handle(self, *args: Any, **options: Any) -> None:
        result = sync_shipments()
        self.stdout.write(
            f"sync_shipments: {result.checked} shipments checked, {result.delivered} delivered, "
            f"{len(result.exceptions)} with an exception, {result.failed} failed"
        )
        if result.failed:
            raise CommandError(f"{result.failed} shipments could not be synced")
