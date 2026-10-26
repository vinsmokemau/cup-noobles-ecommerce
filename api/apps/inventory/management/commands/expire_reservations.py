"""Release the stock holds that lapsed unpaid (SPEC.md §4.8, REQ-012).

A hold lapses when `expires_at < now()`: at `now == expires_at` it is still held. Each order is
handled in its own transaction that takes the order row FOR UPDATE and looks again, so a
webhook approving the same order either wins the lock first (its hold is committed and nothing
is left to release) or finds the hold already released. Running the command twice, or two copies
at once, releases each hold once. Releasing writes no ledger row: `on_hand` did not move.

G37 (ADR-0036): this command owns payment-deadline expiry. A `pending_payment` order is moved
by T5 (`deadline_passed`), whose side effects release its holds; a draft only has its holds
released. `advance_orders` does not fire T5.
"""

import logging
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.inventory import services
from apps.inventory.models import InventoryReservation
from apps.orders.models import Order
from apps.orders.state_machine import GuardFailed, IllegalTransition, apply_event

logger = logging.getLogger(__name__)

# The states in which an order still owns its holds. Any other state settles them itself.
HOLDING_STATES = ("draft", "pending_payment")


def _lapsed_holds():
    return InventoryReservation.objects.filter(
        kind=InventoryReservation.Kind.STOCK,
        state=InventoryReservation.State.HELD,
        expires_at__lt=timezone.now(),
    )


def expire_order(order_id: int) -> bool:
    """Release the lapsed holds of one order. True when it released anything."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        if not _lapsed_holds().filter(order=order).exists():
            return False
        if order.state not in HOLDING_STATES:
            logger.warning(
                "Order %s is %s but holds a lapsed reservation; left alone",
                order.pk,
                order.state,
            )
            return False
        if order.state == "pending_payment":
            apply_event(order.pk, "deadline_passed")
        else:
            services.release_reservations(order, reason="expired")
        return True


class Command(BaseCommand):
    help = "Release stock holds whose expires_at has passed (SPEC.md §4.8)."

    def handle(self, *args: Any, **options: Any) -> None:
        order_ids = sorted(
            _lapsed_holds().values_list("order_id", flat=True).distinct()
        )
        released = 0
        for order_id in order_ids:
            try:
                released += expire_order(order_id)
            except (GuardFailed, IllegalTransition):
                # One order in an odd shape must not stop the others from expiring.
                logger.exception("Order %s could not be expired; left alone", order_id)
        self.stdout.write(f"expire_reservations: {released} order(s) released")
