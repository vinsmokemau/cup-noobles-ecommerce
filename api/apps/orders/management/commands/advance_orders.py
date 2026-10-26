"""Move orders forward on the clock (SPEC.md 8.A, §4.8, REQ-022).

Release 1 runs T12: a `delivered` order completes once 7 days have passed since its last
shipment was delivered (at exactly 7 days, not before). T5 is not fired here: `expire_reservations`
owns payment-deadline expiry (G37, ADR-0036).

Each order goes through `apply_event`, which locks the row and re-reads its state, so running the
command twice, or two copies at once, completes an order once: the loser finds it `completed` and
is skipped. A completed order is no longer `delivered`, so a rerun finds nothing to do.
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


def complete_delivered_orders() -> int:
    """T12 for every order delivered 7 days ago or more. Returns how many it completed."""
    completed = 0
    for order_id in _due_for_completion():
        try:
            apply_event(order_id, "auto_after_7d")
        except IllegalTransition:
            # Another run, or a refund or cancellation, moved it first.
            logger.info("Order %s left `delivered` before it could complete", order_id)
            continue
        completed += 1
    return completed


class Command(BaseCommand):
    help = "Auto-complete delivered orders after 7 days (SPEC.md §4.8, T12)."

    def handle(self, *args: Any, **options: Any) -> None:
        completed = complete_delivered_orders()
        self.stdout.write(f"advance_orders: {completed} order(s) completed")
