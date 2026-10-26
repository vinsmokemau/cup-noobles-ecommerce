"""Find payments whose notification was lost (SPEC.md 9.7, §4.8, REQ-022, REQ-031).

For every order still `pending_payment` after `MIN_AGE`, ask the provider for the order's payments
and pass each through the same path as a webhook (payment row, then the 9.4 mapping). The mapping
re-reads the order under its row lock, so a run overlapping a webhook, or itself, moves the order
once and records the loser as `webhook_no_op` (G14).
"""

import logging
from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.core.providers import payment_provider
from apps.orders.models import Order
from apps.payments.webhooks import process_provider_payment

logger = logging.getLogger(__name__)

MIN_AGE = timedelta(minutes=15)


def reconcile_order(order: Order) -> int:
    """Process every payment the provider holds for `order`; returns how many it found."""
    provider = payment_provider()
    found = provider.find_payments(str(order.public_id))
    for provider_payment in found:
        process_provider_payment(provider.code, provider_payment)
    return len(found)


class Command(BaseCommand):
    help = "Reconcile pending_payment orders with the payment provider (SPEC.md 9.7)."

    def handle(self, *args: Any, **options: Any) -> None:
        cutoff = timezone.now() - MIN_AGE
        orders = Order.objects.filter(
            state="pending_payment", created_at__lt=cutoff
        ).order_by("created_at", "pk")
        checked = payments = failed = 0
        for order in orders:
            checked += 1
            try:
                payments += reconcile_order(order)
            except Exception:  # noqa: BLE001 - one order's failure must not stop the others
                failed += 1
                logger.exception("reconcile_payments failed for order %s", order.number)
        self.stdout.write(
            f"reconcile_payments: {checked} orders checked, {payments} payments found, "
            f"{failed} failed"
        )
        if failed:
            raise CommandError(f"{failed} orders could not be reconciled")
