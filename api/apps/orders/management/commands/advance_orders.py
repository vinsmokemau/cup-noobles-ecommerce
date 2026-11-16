"""Move orders forward on the clock (SPEC.md 8.A, §4.8, REQ-022).

Release 1 runs two transitions:

- T7: a `paid` delivery order moves to `preparing` with no staff step (G75, ADR-0075). Staff can
  still press "Pasar a preparación" in the admin before the job gets to it.
- T12: a `delivered` order completes once 7 days have passed since its last shipment was
  delivered (at exactly 7 days, not before).

T5 is not fired here: `expire_reservations` owns payment-deadline expiry (G37, ADR-0036).

Each order goes through `apply_event`, which locks the row and re-reads its state, so running the
command twice, or two copies at once, moves an order once: the loser finds it already moved and
skips it. A moved order has left the state the job looks for, so a rerun finds nothing to do.
"""

import logging
from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand
from django.db.models import Max
from django.utils import timezone

from apps.orders.models import Order
from apps.orders.state_machine import IllegalTransition, apply_event

logger = logging.getLogger(__name__)

AUTO_COMPLETE_AFTER = timedelta(days=7)


def _due_for_completion() -> list[int]:
    cutoff = timezone.now() - AUTO_COMPLETE_AFTER
    return list(
        Order.objects.filter(state="delivered")
        .annotate(delivered=Max("shipments__delivered_at"))
        .filter(delivered__lte=cutoff)
        .order_by("pk")
        .values_list("pk", flat=True)
    )


def _paid_delivery_orders() -> list[int]:
    return list(
        Order.objects.filter(
            state="paid", fulfillment_method=Order.FulfillmentMethod.DELIVERY
        )
        .order_by("pk")
        .values_list("pk", flat=True)
    )


def _fire(order_ids: list[int], event: str, *, moved_first: str, failed: str) -> int:
    """Fire `event` for each order, one transaction per order. Returns how many moved."""
    moved = 0
    for order_id in order_ids:
        try:
            apply_event(order_id, event)
        except IllegalTransition:
            # Another run, or a refund or cancellation, moved it first.
            logger.info(moved_first, order_id)
            continue
        except Exception:
            # One order in an odd shape must not stop the ones after it (G47). `apply_event`
            # rolled its own transaction back, so the order is as it was.
            logger.exception(failed, order_id)
            continue
        moved += 1
    return moved


def prepare_paid_orders() -> int:
    """T7 for every `paid` delivery order (G75). Returns how many it moved to `preparing`."""
    return _fire(
        _paid_delivery_orders(),
        "auto",
        moved_first="Order %s left `paid` before it could move to preparing",
        failed="Order %s could not be moved to preparing; left alone",
    )


def complete_delivered_orders() -> int:
    """T12 for every order delivered 7 days ago or more. Returns how many it completed."""
    return _fire(
        _due_for_completion(),
        "auto_after_7d",
        moved_first="Order %s left `delivered` before it could complete",
        failed="Order %s could not be completed; left alone",
    )


class Command(BaseCommand):
    help = (
        "Move paid delivery orders to preparing (T7) and auto-complete delivered orders "
        "after 7 days (T12) (SPEC.md §4.8)."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        prepared = prepare_paid_orders()
        completed = complete_delivered_orders()
        self.stdout.write(
            f"advance_orders: {prepared} order(s) moved to preparing, "
            f"{completed} order(s) completed"
        )
